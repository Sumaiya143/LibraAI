"""Manual payout review ledger. This module NEVER transfers funds."""
import sqlite3
from decimal import Decimal, InvalidOperation

ALLOWED = {'manual_review': {'approved', 'rejected'}, 'approved': {'paid', 'rejected'}, 'rejected': set(), 'paid': set()}

def install(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS payout_review_events (
      id INTEGER PRIMARY KEY, payout_id INTEGER NOT NULL, reviewer_id INTEGER NOT NULL,
      previous_status TEXT NOT NULL, new_status TEXT NOT NULL,
      reference TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP)''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_payout_review_events_payout ON payout_review_events(payout_id)')

def review(conn, payout_id, reviewer_id, status, reference=''):
    """Record a manual review decision, not a gateway disbursement."""
    if type(payout_id) is not int or payout_id <= 0 or type(reviewer_id) is not int or reviewer_id <= 0:
        raise ValueError('Invalid identifier')
    if status not in ('approved', 'rejected', 'paid') or not isinstance(reference, str) or len(reference) > 120:
        raise ValueError('Invalid decision or reference')
    if status == 'paid' and not reference.strip():
        raise ValueError('External payment reference required')
    install(conn)
    conn.execute('SAVEPOINT payout_review')
    try:
        row = conn.execute('SELECT merchant_id,amount,currency,status FROM merchant_payouts WHERE id=?', (payout_id,)).fetchone()
        if row is None:
            raise LookupError('Payout not found')
        merchant_id, amount, currency, old = row
        if merchant_id == reviewer_id:
            raise PermissionError('Self review is forbidden')
        try:
            money = Decimal(str(amount))
            if not money.is_finite() or money <= 0 or money.as_tuple().exponent < -2:
                raise ValueError('Invalid amount')
        except (InvalidOperation, TypeError):
            raise ValueError('Invalid amount')
        if currency != 'BDT' or status not in ALLOWED.get(old, set()):
            raise ValueError('Invalid payout transition')
        conn.execute('UPDATE merchant_payouts SET status=? WHERE id=? AND status=?', (status, payout_id, old))
        if conn.execute('SELECT changes()').fetchone()[0] != 1:
            raise RuntimeError('Concurrent update detected')
        conn.execute('INSERT INTO payout_review_events(payout_id,reviewer_id,previous_status,new_status,reference) VALUES(?,?,?,?,?)',
                     (payout_id, reviewer_id, old, status, reference.strip() or None))
        conn.execute('RELEASE SAVEPOINT payout_review')
        return {'payout_id': payout_id, 'status': status, 'notice': 'Manual ledger update only; no funds were transferred'}
    except Exception:
        conn.execute('ROLLBACK TO SAVEPOINT payout_review')
        conn.execute('RELEASE SAVEPOINT payout_review')
        raise
