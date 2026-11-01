"""Read-only, bounded admin payout ledger. No bank or gateway transfers."""

def list_payouts(conn, limit=50):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Limit must be between 1 and 100')
    payouts = [dict(row) for row in conn.execute(
        'SELECT id,merchant_id,amount,currency,status,created FROM merchant_payouts ORDER BY id DESC LIMIT ?', (limit,))]
    events = [dict(row) for row in conn.execute(
        '''SELECT e.id,e.payout_id,e.reviewer_id,e.previous_status,e.new_status,e.reference,e.created
           FROM payout_review_events e ORDER BY e.id DESC LIMIT ?''', (limit,))]
    return {'payouts': payouts, 'review_events': events,
            'notice': 'Manual ledger only. Paid status is not proof of fund settlement.'}
