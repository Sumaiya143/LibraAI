"""Read-only refund integrity audit. Reports anomalies; never changes payment state."""
import argparse
import json
import sqlite3
from pathlib import Path


def audit_refunds(conn, limit=500, offset=0):
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError('limit must be 1..500')
    if type(offset) is not int or offset < 0 or offset > 1000000000:
        raise ValueError('offset must be 0..1000000000')
    conn.row_factory = sqlite3.Row
    rows = conn.execute('''SELECT id,order_id,attempt_id,amount_cents,state,provider_ref
                           FROM refund_requests ORDER BY id DESC LIMIT ? OFFSET ?''', (limit, offset)).fetchall()
    issues = []
    for r in rows:
        problems = []
        if type(r['amount_cents']) is not int or r['amount_cents'] <= 0:
            problems.append('invalid_refund_amount')
        order = conn.execute('SELECT id FROM orders WHERE id=?', (r['order_id'],)).fetchone()
        if not order:
            problems.append('missing_order')
        attempt = conn.execute('SELECT order_id,amount_cents,state FROM payment_attempts WHERE id=?', (r['attempt_id'],)).fetchone()
        if not attempt:
            problems.append('missing_payment_attempt')
        else:
            if attempt['order_id'] != r['order_id']:
                problems.append('attempt_order_mismatch')
            paid_count = conn.execute("SELECT COUNT(*) FROM payment_attempts WHERE order_id=? AND state='paid'", (r['order_id'],)).fetchone()[0]
            if paid_count > 1:
                problems.append('multiple_paid_attempts')
            if attempt['state'] != 'paid':
                problems.append('attempt_not_paid')
            allocated = conn.execute('''SELECT COALESCE(SUM(amount_cents),0) FROM refund_requests
                                        WHERE attempt_id=? AND state!='rejected' ''', (r['attempt_id'],)).fetchone()[0]
            if allocated > attempt['amount_cents']:
                problems.append('refunds_exceed_payment')
        if r['state'] not in ('requested', 'approved', 'rejected', 'refunded'):
            problems.append('invalid_refund_state')
        # Provider refund references must be unique among confirmed refunds.
        # A repeated reference can otherwise conceal duplicate settlement records.
        if r['state'] == 'refunded' and r['provider_ref']:
            duplicates = conn.execute(
                "SELECT COUNT(*) FROM refund_requests WHERE state='refunded' AND provider_ref=?",
                (r['provider_ref'],)).fetchone()[0]
            if duplicates > 1:
                problems.append('duplicate_confirmed_provider_reference')
        # An already refunded record must never reference an unpaid attempt.
        if r['state'] == 'refunded' and attempt and attempt['state'] != 'paid':
            problems.append('refunded_against_unpaid_attempt')
        if r['state'] == 'refunded' and not r['provider_ref']:
            problems.append('confirmed_refund_missing_provider_reference')
        if r['state'] != 'refunded' and r['provider_ref']:
            problems.append('unconfirmed_refund_has_provider_reference')
        if problems:
            issues.append({'refund_id': r['id'], 'order_id': r['order_id'], 'issues': sorted(set(problems))})
    return {'checked': len(rows), 'offset': offset, 'limit': limit,
            'has_more': len(conn.execute('SELECT id FROM refund_requests ORDER BY id DESC LIMIT 1 OFFSET ?',
                                         (offset + len(rows),)).fetchall()) > 0,
            'issue_count': len(issues), 'issues': issues, 'read_only': True}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only refund anomaly report')
    parser.add_argument('--db', required=True)
    parser.add_argument('--limit', type=int, default=500)
    parser.add_argument('--offset', type=int, default=0)
    args = parser.parse_args(argv)
    db = Path(args.db)
    if not db.is_file():
        parser.error('Database file does not exist')
    if not 1 <= args.limit <= 500:
        parser.error('--limit must be 1..500')
    if not 0 <= args.offset <= 1000000000:
        parser.error('--offset must be 0..1000000000')
    with sqlite3.connect('file:' + db.resolve().as_posix() + '?mode=ro', uri=True) as conn:
        report = audit_refunds(conn, args.limit, args.offset)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report['issue_count'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
