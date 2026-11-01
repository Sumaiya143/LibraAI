"""Complete (bounded) payout audit snapshot, refusing silent truncation."""

MAX_EXPORT_ROWS = 10000

class ExportTooLarge(ValueError):
    pass

def export_snapshot(conn, max_rows=MAX_EXPORT_ROWS):
    if type(max_rows) is not int or not 1 <= max_rows <= MAX_EXPORT_ROWS:
        raise ValueError('Invalid export limit')
    # One read transaction ensures both tables are captured consistently.
    conn.execute('SAVEPOINT payout_export_snapshot')
    try:
        payouts = [dict(row) for row in conn.execute(
            'SELECT id,merchant_id,amount,currency,status,created FROM merchant_payouts ORDER BY id ASC LIMIT ?', (max_rows+1,))]
        events = [dict(row) for row in conn.execute(
            'SELECT id,payout_id,reviewer_id,previous_status,new_status,reference,created FROM payout_review_events ORDER BY id ASC LIMIT ?', (max_rows+1,))]
        if len(payouts) > max_rows or len(events) > max_rows:
            raise ExportTooLarge('Ledger exceeds safe CSV export limit; no partial export produced')
        return {'payouts': payouts, 'review_events': events}
    finally:
        conn.execute('ROLLBACK TO SAVEPOINT payout_export_snapshot')
        conn.execute('RELEASE SAVEPOINT payout_export_snapshot')
