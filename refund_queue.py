"""Bounded, privacy-minimized administrative refund work queue (read only)."""
from refund_engine import RefundError

STATES = frozenset(('requested', 'approved', 'rejected', 'refunded'))

def list_refund_queue(conn, *, state='requested', limit=50, offset=0):
    if state != 'all' and state not in STATES:
        raise RefundError('Invalid refund state filter')
    if type(limit) is not int or not 1 <= limit <= 100:
        raise RefundError('Limit must be 1–100')
    if type(offset) is not int or not 0 <= offset <= 1_000_000:
        raise RefundError('Invalid offset')
    clause = '' if state == 'all' else 'WHERE r.state = ?'
    params = () if state == 'all' else (state,)
    total = conn.execute('SELECT COUNT(*) FROM refund_requests r ' + clause, params).fetchone()[0]
    rows = conn.execute('''SELECT r.id, r.order_id, r.amount_cents, r.state,
                         r.created, r.updated, p.provider
                         FROM refund_requests r
                         JOIN payment_attempts p ON p.id = r.attempt_id
                         ''' + clause + ''' ORDER BY r.created ASC, r.id ASC
                         LIMIT ? OFFSET ?''', params + (limit, offset)).fetchall()
    items = [dict(row) if hasattr(row, 'keys') else dict(zip(
        ('id','order_id','amount_cents','state','created','updated','provider'), row)) for row in rows]
    return {'state': state, 'limit': limit, 'offset': offset,
            'total': total, 'has_more': offset + len(items) < total, 'items': items}
