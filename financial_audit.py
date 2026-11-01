"""Read-only accounting consistency checks. Does not settle payments or issue refunds."""
import argparse
import json
import sqlite3
from pathlib import Path

PAID_ORDER_STATES = ('Paid — fulfillment pending', 'Processing', 'Fulfilled', 'Completed')

def audit(conn):
    conn.row_factory = sqlite3.Row
    findings = []
    def check(code, query, explanation):
        try:
            rows = conn.execute(query).fetchall()
        except sqlite3.OperationalError as exc:
            findings.append({'code': 'schema_missing', 'check': code, 'detail': str(exc)[:120]})
            return
        for row in rows:
            findings.append({'code': code, 'order_id': row['order_id'], 'detail': explanation})

    check('paid_without_verified_attempt', '''SELECT o.id AS order_id FROM orders o
      WHERE o.status IN ('Paid — fulfillment pending','Processing','Fulfilled','Completed')
      AND NOT EXISTS(SELECT 1 FROM payment_attempts p WHERE p.order_id=o.id AND p.state='paid')''',
      'Paid order has no verified paid payment attempt')
    check('multiple_paid_attempts', '''SELECT order_id FROM payment_attempts
      WHERE state='paid' GROUP BY order_id HAVING COUNT(*)>1''',
      'Multiple paid payment attempts for one order')
    check('paid_attempt_unpaid_order', '''SELECT p.order_id FROM payment_attempts p
      JOIN orders o ON o.id=p.order_id WHERE p.state='paid'
      AND o.status IN ('Awaiting payment','Awaiting payment — sandbox only','Cancelled')''',
      'Gateway-paid attempt has an unpaid or cancelled order; requires manual reconciliation')
    check('payment_amount_mismatch', '''SELECT p.order_id FROM payment_attempts p
      JOIN orders o ON o.id=p.order_id WHERE p.state='paid'
      AND (p.amount_cents != CAST(ROUND(o.total*100) AS INTEGER) OR p.currency!='BDT')''',
      'Verified payment amount or currency differs from recorded order')
    check('entitlement_without_paid_order', '''SELECT e.order_id FROM digital_entitlements e
      JOIN orders o ON o.id=e.order_id WHERE o.status NOT IN
      ('Paid — fulfillment pending','Processing','Fulfilled','Completed')''',
      'Entitlement exists for a non-paid order; access must remain blocked')
    return {'ok': not findings, 'findings': findings, 'checked': 5}

def audit_path(path):
    p = Path(path)
    if not p.is_file():
        return {'ok': False, 'findings': [{'code':'database_missing','detail':'Database file not found'}], 'checked':0}
    with sqlite3.connect(f'file:{p.resolve()}?mode=ro', uri=True) as conn:
        return audit(conn)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Read-only LibraAI financial ledger audit')
    parser.add_argument('--db', required=True)
    args = parser.parse_args()
    result = audit_path(args.db)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['ok'] else 1)
