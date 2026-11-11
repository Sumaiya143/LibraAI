"""Transactional physical-library lending for LibraAI.

Circulation inventory is intentionally separate from retail stock so selling a
copy can never accidentally create or consume a library loan.
"""
from datetime import date, datetime, timedelta, timezone

MAX_ACTIVE_LOANS = 5
LOAN_DAYS = 14
MAX_RENEWALS = 1

class CirculationError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def setup(conn_factory):
    conn = conn_factory()
    try:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS library_inventory (
            id INTEGER PRIMARY KEY,
            book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            branch TEXT NOT NULL DEFAULT 'Central',
            total_copies INTEGER NOT NULL DEFAULT 0 CHECK(total_copies >= 0),
            available_copies INTEGER NOT NULL DEFAULT 0 CHECK(available_copies >= 0 AND available_copies <= total_copies),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(book_id, branch)
        );
        CREATE INDEX IF NOT EXISTS idx_library_inventory_available ON library_inventory(book_id, available_copies);
        ''')
        columns = {r['name'] for r in conn.execute('PRAGMA table_info(loans)').fetchall()}
        if 'renew_count' not in columns:
            conn.execute('ALTER TABLE loans ADD COLUMN renew_count INTEGER NOT NULL DEFAULT 0')
        if 'returned_at' not in columns:
            conn.execute('ALTER TABLE loans ADD COLUMN returned_at TEXT')
        if 'checked_out_at' not in columns:
            conn.execute('ALTER TABLE loans ADD COLUMN checked_out_at TEXT')
        conn.execute("CREATE INDEX IF NOT EXISTS idx_loans_user_status ON loans(user_id,status,due)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_loans_book_status ON loans(book_id,status)")
        from library_fines import setup as setup_fines
        setup_fines(conn)
        # Existing catalog stock is used only to seed initial library copies once.
        conn.execute('''INSERT OR IGNORE INTO library_inventory(book_id,branch,total_copies,available_copies)
            SELECT id,COALESCE(NULLIF(branch,''),'Central'),MAX(0,COALESCE(stock,0)),MAX(0,COALESCE(stock,0)) FROM books''')
    finally:
        conn.close()


def _ensure_inventory(conn, book_id):
    row = conn.execute('SELECT id FROM library_inventory WHERE book_id=? ORDER BY id LIMIT 1', (book_id,)).fetchone()
    if row:
        return
    book = conn.execute('SELECT branch,stock FROM books WHERE id=?', (book_id,)).fetchone()
    if not book:
        raise CirculationError('not_found', 'Book not found.')
    branch = (book['branch'] or 'Central').strip()[:80] or 'Central'
    copies = max(0, int(book['stock'] or 0))
    conn.execute('''INSERT OR IGNORE INTO library_inventory(book_id,branch,total_copies,available_copies)
        VALUES(?,?,?,?)''', (book_id, branch, copies, copies))


def borrow_book(conn, user_id, book_id, now=None):
    now = now or datetime.now(timezone.utc)
    from library_fines import policy_date
    today_date = policy_date(now)
    today = today_date.isoformat()
    conn.execute('BEGIN IMMEDIATE')
    try:
        book = conn.execute('SELECT id,branch FROM books WHERE id=?', (book_id,)).fetchone()
        if not book:
            raise CirculationError('not_found', 'Book not found.')
        active = conn.execute("SELECT COUNT(*) FROM loans WHERE user_id=? AND lower(status) IN ('borrowed','renewed')", (user_id,)).fetchone()[0]
        if active >= MAX_ACTIVE_LOANS:
            raise CirculationError('loan_limit', f'You can have up to {MAX_ACTIVE_LOANS} active borrowed books.')
        duplicate = conn.execute("SELECT 1 FROM loans WHERE user_id=? AND book_id=? AND lower(status) IN ('borrowed','renewed') LIMIT 1", (user_id,book_id)).fetchone()
        if duplicate:
            raise CirculationError('already_borrowed', 'You already have this book borrowed.')
        from library_fines import outstanding_balance
        unpaid = outstanding_balance(conn, user_id, now.date())
        if unpaid > 0:
            raise CirculationError('fine_due', f'Unpaid library fine: BDT {unpaid / 100:.2f}. Pay and verify the fine before borrowing another book.')
        _ensure_inventory(conn, book_id)
        stock = conn.execute('SELECT id,branch,available_copies FROM library_inventory WHERE book_id=? AND available_copies>0 ORDER BY CASE WHEN branch=? THEN 0 ELSE 1 END,id LIMIT 1', (book_id,book['branch'] or 'Central')).fetchone()
        if not stock:
            raise CirculationError('unavailable', 'No library copy is currently available to borrow.')
        changed = conn.execute('UPDATE library_inventory SET available_copies=available_copies-1,updated_at=CURRENT_TIMESTAMP WHERE id=? AND available_copies>0', (stock['id'],)).rowcount
        if changed != 1:
            raise CirculationError('unavailable', 'This copy was just borrowed by another reader. Please try again.')
        due = (today_date + timedelta(days=LOAN_DAYS)).isoformat()
        created = now.astimezone(timezone.utc).isoformat(timespec='seconds')
        cur = conn.execute("INSERT INTO loans(user_id,book_id,status,due,branch,created,checked_out_at) VALUES(?,?,'Borrowed',?,?,?,?)", (user_id,book_id,due,stock['branch'],created,created))
        conn.commit()
        return {'loan_id': cur.lastrowid, 'due': due, 'branch': stock['branch']}
    except Exception:
        conn.rollback()
        raise


def update_loan(conn, loan_id, action, user_id=None, now=None):
    if action not in ('renew','return'):
        raise CirculationError('invalid_action', 'Unsupported loan action.')
    now = now or datetime.now(timezone.utc)
    from library_fines import policy_date
    today_date = policy_date(now)
    today = today_date.isoformat()
    conn.execute('BEGIN IMMEDIATE')
    try:
        sql = 'SELECT * FROM loans WHERE id=?' + (' AND user_id=?' if user_id is not None else '')
        args = (loan_id,user_id) if user_id is not None else (loan_id,)
        loan = conn.execute(sql, args).fetchone()
        if loan is None:
            raise CirculationError('not_found', 'Loan not found.')
        if str(loan['status']).lower() == 'returned':
            raise CirculationError('already_returned', 'This book has already been returned.')
        if action == 'renew':
            if str(loan['status']).lower() not in ('borrowed','renewed'):
                raise CirculationError('not_renewable', 'This loan cannot be renewed.')
            if loan['due'] and loan['due'] < today:
                raise CirculationError('overdue', 'Overdue books cannot be renewed online. Please contact the library.')
            renew_count = int(loan['renew_count'] or 0) if 'renew_count' in loan.keys() else 0
            if renew_count >= MAX_RENEWALS:
                raise CirculationError('renewal_limit', 'This book has reached its renewal limit.')
            conn.execute("UPDATE loans SET due=date(CASE WHEN due IS NULL OR due<? THEN ? ELSE due END,'+14 day'),status='Renewed',renew_count=renew_count+1 WHERE id=?", (today,today,loan_id))
            conn.commit()
            return {'due': conn.execute('SELECT due FROM loans WHERE id=?',(loan_id,)).fetchone()['due']}
        changed = conn.execute("UPDATE loans SET status='Returned',returned_at=? WHERE id=? AND lower(status)!='returned'", (now.astimezone(timezone.utc).isoformat(timespec='seconds'),loan_id)).rowcount
        if changed != 1:
            raise CirculationError('already_returned', 'This book has already been returned.')
        _ensure_inventory(conn, loan['book_id'])
        loan_branch = (loan['branch'] or 'Central').strip()[:80] or 'Central'
        inv = conn.execute('SELECT id FROM library_inventory WHERE book_id=? AND branch=?', (loan['book_id'],loan_branch)).fetchone()
        if not inv:
            # Backfill a branch bucket for legacy loans whose original inventory
            # was not recorded, then check the returned copy back in exactly once.
            conn.execute('INSERT INTO library_inventory(book_id,branch,total_copies,available_copies) VALUES(?,?,1,0)', (loan['book_id'],loan_branch))
            inv = conn.execute('SELECT id FROM library_inventory WHERE book_id=? AND branch=?', (loan['book_id'],loan_branch)).fetchone()
        conn.execute('UPDATE library_inventory SET total_copies=MAX(total_copies,available_copies+1),available_copies=available_copies+1,updated_at=CURRENT_TIMESTAMP WHERE id=?', (inv['id'],))
        from library_fines import assess_user_fines, outstanding_balance
        assess_user_fines(conn, loan['user_id'], today_date)
        fine_row = conn.execute("SELECT COALESCE(amount_paise,0) FROM library_fines WHERE loan_id=? AND status='unpaid'", (loan_id,)).fetchone()
        fine_amount = int(fine_row[0]) if fine_row else 0
        balance_row = conn.execute(
            "SELECT COALESCE(SUM(amount_paise),0) FROM library_fines WHERE user_id=? AND status='unpaid'",
            (loan['user_id'],),
        ).fetchone()
        balance = int(balance_row[0] or 0)
        conn.commit()
        return {'returned': True, 'fine_amount_paise': fine_amount, 'outstanding_balance_paise': balance}
    except Exception:
        conn.rollback()
        raise
