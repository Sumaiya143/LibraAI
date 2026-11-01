"""Rights-gated digital access; issued only for verified paid order lines."""
from datetime import datetime, timezone

DIGITAL_FORMATS = {'ebook', 'e-book', 'digital', 'pdf', 'epub', 'audio', 'audiobook', 'audio book'}

def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS digital_entitlements (
        id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, book_id INTEGER NOT NULL,
        order_id INTEGER NOT NULL, granted_at TEXT NOT NULL,
        UNIQUE(user_id, book_id, order_id))''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_entitlement_user_book ON digital_entitlements(user_id,book_id)')
    conn.commit()

def has_access(conn, user_id, book_id):
    '''Require a paid licensed entitlement with at least one non-fully-refunded digital line.

    Legacy databases without item allocation tables retain order-level behavior.
    '''
    if type(user_id) is not int or user_id <= 0 or type(book_id) is not int or book_id <= 0:
        return False
    # Audio assets have their own explicit rights record; eBooks continue to use
    # licensed_documents. The table-existence guard keeps older DB migrations safe.
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('audiobook_assets')")}
    audio_clause = " OR EXISTS (SELECT 1 FROM audiobook_assets a WHERE a.book_id=e.book_id AND a.active=1 AND a.license_status='active' AND a.access_policy='licensed' AND (a.license_expires_at IS NULL OR a.license_expires_at > CURRENT_TIMESTAMP))" if 'audiobook_assets' in tables else ''
    grants = conn.execute(f'''SELECT e.order_id FROM digital_entitlements e
        JOIN orders o ON o.id=e.order_id
        WHERE e.user_id=? AND e.book_id=? AND o.user_id=?
          AND o.status IN ('Paid — fulfillment pending','Processing','Fulfilled','Completed')
          AND (EXISTS (SELECT 1 FROM licensed_documents d WHERE d.book_id=e.book_id AND d.access_policy='licensed'){audio_clause})''',
        (user_id,book_id,user_id)).fetchall()
    if not grants:
        return False
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('refund_item_allocations','refund_requests')")}
    columns = {r[1] for r in conn.execute('PRAGMA table_info(order_items)')}
    has_paid_line_total = 'line_total_cents' in columns
    if tables != {'refund_item_allocations','refund_requests'} or not {'id','unit_price_cents','quantity'}.issubset(columns):
        return True  # Legacy orders have no immutable per-item price snapshots.
    for grant in grants:
        line_columns = 'id,unit_price_cents,quantity,format' + (',line_total_cents' if has_paid_line_total else '')
        lines = conn.execute(f'SELECT {line_columns} FROM order_items WHERE order_id=? AND book_id=?',
                             (grant['order_id'],book_id)).fetchall()
        for line in lines:
            if not isinstance(line['format'],str) or line['format'].strip().lower() not in DIGITAL_FORMATS:
                continue
            cap = (line['line_total_cents'] if has_paid_line_total and line['line_total_cents'] is not None
                   else line['unit_price_cents'] * line['quantity'])
            if cap <= 0:
                continue
            refunded = conn.execute('''SELECT COALESCE(SUM(a.amount_cents),0)
                FROM refund_item_allocations a JOIN refund_requests r ON r.id=a.refund_id
                WHERE a.order_item_id=? AND r.state='refunded' ''',(line['id'],)).fetchone()[0]
            if refunded < cap:
                return True
    return False

def grant_paid_order(conn, order_id):
    """Called inside the same transaction as verified payment settlement; no commit here."""
    order=conn.execute('SELECT user_id,status FROM orders WHERE id=?',(order_id,)).fetchone()
    if not order or order['status']!='Paid — fulfillment pending':
        raise ValueError('Verified paid order required')
    rows=conn.execute('''SELECT DISTINCT oi.book_id,oi.format FROM order_items oi
        WHERE oi.order_id=?''',(order_id,)).fetchall()
    granted=0
    for item in rows:
        if item['format'].strip().lower() not in DIGITAL_FORMATS:
            continue
        licensed=conn.execute("SELECT 1 FROM licensed_documents WHERE book_id=? AND access_policy='licensed' LIMIT 1",(item['book_id'],)).fetchone()
        if not licensed:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audiobook_assets'")}
            if tables:
                licensed=conn.execute("SELECT 1 FROM audiobook_assets WHERE book_id=? AND active=1 AND license_status='active' AND access_policy='licensed' AND (license_expires_at IS NULL OR license_expires_at > CURRENT_TIMESTAMP) LIMIT 1",(item['book_id'],)).fetchone()
        if not licensed:
            continue
        result=conn.execute('''INSERT OR IGNORE INTO digital_entitlements
            (user_id,book_id,order_id,granted_at) VALUES(?,?,?,?)''',
            (order['user_id'],item['book_id'],order_id,datetime.now(timezone.utc).isoformat()))
        granted+=result.rowcount
    return granted


def reconcile_historical_paid_orders(conn, limit=5000):
    """Idempotently backfill missing entitlements for already-paid historical orders.

    Does not change payment/order state. Access remains subject to has_access(),
    including per-item refund allocation and active license checks.
    Intended for an explicitly invoked admin maintenance operation.
    """
    limit = max(1, min(20000, int(limit)))
    orders = conn.execute("""SELECT id,user_id FROM orders
        WHERE status IN ('Paid — fulfillment pending','Processing','Fulfilled','Completed')
        ORDER BY id LIMIT ?""", (limit,)).fetchall()
    granted = 0
    for order in orders:
        lines = conn.execute('SELECT DISTINCT book_id,format FROM order_items WHERE order_id=?', (order['id'],)).fetchall()
        for item in lines:
            fmt = (item['format'] or '').strip().lower()
            if fmt not in DIGITAL_FORMATS:
                continue
            licensed = conn.execute("SELECT 1 FROM licensed_documents WHERE book_id=? AND access_policy='licensed' LIMIT 1", (item['book_id'],)).fetchone()
            if not licensed:
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audiobook_assets'")}
                if tables:
                    licensed = conn.execute("""SELECT 1 FROM audiobook_assets WHERE book_id=? AND active=1
                        AND license_status='active' AND access_policy='licensed'
                        AND (license_expires_at IS NULL OR license_expires_at > CURRENT_TIMESTAMP) LIMIT 1""", (item['book_id'],)).fetchone()
            if not licensed:
                continue
            cur = conn.execute('''INSERT OR IGNORE INTO digital_entitlements
                (user_id,book_id,order_id,granted_at) VALUES(?,?,?,?)''',
                (order['user_id'], item['book_id'], order['id'], datetime.now(timezone.utc).isoformat()))
            granted += cur.rowcount
    return {'orders_scanned': len(orders), 'entitlements_granted': granted, 'limit': limit}
