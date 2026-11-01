"""Read-only payment/order/entitlement reconciliation for commercial operations."""
import argparse
import json
import sqlite3


def audit(conn, limit=500, offset=0):
    if type(limit) is not int or not 1 <= limit <= 5000 or type(offset) is not int or offset < 0:
        raise ValueError('Invalid pagination')
    rows = conn.execute('''SELECT a.id,a.order_id,a.amount_cents,a.state,a.provider_ref,
        o.id AS found_order,o.status AS order_status,o.total AS order_total
        FROM payment_attempts a LEFT JOIN orders o ON o.id=a.order_id
        ORDER BY a.id LIMIT ? OFFSET ?''', (limit+1, offset)).fetchall()
    has_more = len(rows) > limit
    anomalies=[]
    for r in rows[:limit]:
        aid,oid,amount,state,provider_ref,found,status,total = r
        issues=[]
        if found is None:
            issues.append('missing_order')
        if type(amount) is not int or amount <= 0:
            issues.append('invalid_payment_amount')
        if state == 'paid' and not provider_ref:
            issues.append('paid_without_provider_reference')
        if state == 'paid' and status in ('Awaiting payment','Awaiting payment — sandbox only'):
            issues.append('paid_attempt_unpaid_order')
        if found is not None:
            try:
                from payment_engine import payable_order_cents
                expected=payable_order_cents(conn,oid,total)
                if expected != amount:
                    issues.append('order_amount_mismatch')
            except (ValueError, TypeError, sqlite3.Error):
                issues.append('order_ledger_invalid')
        if issues:
            anomalies.append({'attempt_id':aid,'order_id':oid,'issues':issues})
    return {'checked':min(len(rows),limit),'offset':offset,'limit':limit,'has_more':has_more,'anomalies':anomalies}


def main():
    p=argparse.ArgumentParser(description='Read-only payment reconciliation audit')
    p.add_argument('--db',required=True)
    p.add_argument('--limit',type=int,default=500)
    p.add_argument('--offset',type=int,default=0)
    args=p.parse_args()
    conn=sqlite3.connect('file:'+__import__('pathlib').Path(args.db).resolve().as_posix()+'?mode=ro',uri=True)
    try:
        result=audit(conn,args.limit,args.offset)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if result['anomalies'] else 0
    finally:
        conn.close()

if __name__=='__main__':
    raise SystemExit(main())
