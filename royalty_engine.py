"""Idempotent, integer-cent royalty accrual for completed paid order items.

Accounting only: does not transfer money or imply rights to a book.
"""
from decimal import Decimal, ROUND_HALF_UP


def setup(conn):
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS royalty_contracts (
      book_id INTEGER PRIMARY KEY, creator_user_id INTEGER NOT NULL,
      royalty_bps INTEGER NOT NULL CHECK(royalty_bps BETWEEN 0 AND 10000),
      active INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS royalty_ledger (
      id INTEGER PRIMARY KEY, order_item_id INTEGER NOT NULL UNIQUE,
      order_id INTEGER NOT NULL, book_id INTEGER NOT NULL,
      creator_user_id INTEGER NOT NULL, gross_cents INTEGER NOT NULL,
      royalty_cents INTEGER NOT NULL, recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    ''')


def cents(value):
    v = Decimal(str(value))
    if not v.is_finite() or v < 0:
        raise ValueError('Invalid nonnegative monetary amount')
    return int((v * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def accrue(conn, order_item_id, order_id, book_id, gross_amount):
    """Record one royalty per paid item, transaction controlled by caller."""
    gross = cents(gross_amount)
    contract = conn.execute('SELECT creator_user_id,royalty_bps FROM royalty_contracts WHERE book_id=? AND active=1', (book_id,)).fetchone()
    if contract is None:
        return None
    creator, bps = contract
    if not 0 <= bps <= 10000:
        raise ValueError('Invalid contract')
    royalty = (gross * bps + 5000) // 10000
    conn.execute('''INSERT OR IGNORE INTO royalty_ledger
      (order_item_id,order_id,book_id,creator_user_id,gross_cents,royalty_cents)
      VALUES(?,?,?,?,?,?)''', (order_item_id,order_id,book_id,creator,gross,royalty))
    return conn.execute('SELECT royalty_cents FROM royalty_ledger WHERE order_item_id=?',(order_item_id,)).fetchone()[0]


def creator_report(conn, creator_id):
    rows = conn.execute('''SELECT book_id, COUNT(*) AS items, SUM(gross_cents) AS gross_cents,
      SUM(royalty_cents) AS royalty_cents FROM royalty_ledger
      WHERE creator_user_id=? GROUP BY book_id ORDER BY royalty_cents DESC''',(creator_id,)).fetchall()
    return [dict(book_id=r[0], items=r[1], gross_cents=r[2], royalty_cents=r[3]) for r in rows]
