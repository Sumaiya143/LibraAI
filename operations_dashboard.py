"""Read-only admin operational snapshot. No gateway actions or secrets."""
from datetime import datetime, timezone
from financial_audit import audit


def snapshot(conn):
    """Fail closed on missing schema; expose aggregate counts only."""
    conn.row_factory = __import__('sqlite3').Row
    tables = {r['name'] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {'orders', 'payment_attempts', 'refund_requests', 'digital_entitlements'}
    missing = sorted(required - tables)
    if missing:
        return {'ready': False, 'missing_tables': missing, 'counts': {}, 'financial_audit': {'ok': False, 'findings': []}}
    def count(query):
        return int(conn.execute(query).fetchone()[0])
    counts = {
        'total_orders': count('SELECT COUNT(*) FROM orders'),
        'awaiting_payment': count("SELECT COUNT(*) FROM orders WHERE status IN ('Awaiting payment','Awaiting payment — sandbox only')"),
        'paid_orders': count("SELECT COUNT(*) FROM orders WHERE status IN ('Paid — fulfillment pending','Processing','Fulfilled','Completed')"),
        'pending_payment_attempts': count("SELECT COUNT(*) FROM payment_attempts WHERE state IN ('created','pending')"),
        'verified_payment_attempts': count("SELECT COUNT(*) FROM payment_attempts WHERE state='paid'"),
        'refund_requests_needing_review': count("SELECT COUNT(*) FROM refund_requests WHERE state='requested'"),
        'active_digital_entitlements': count("""SELECT COUNT(*) FROM digital_entitlements e JOIN orders o ON o.id=e.order_id
          WHERE o.status IN ('Paid — fulfillment pending','Processing','Fulfilled','Completed')"""),
    }
    result = audit(conn)
    return {'ready': bool(result['ok']), 'missing_tables': [], 'counts': counts,
            'financial_audit': {'ok': result['ok'], 'findings': result['findings'][:25],
                                'total_findings': len(result['findings'])},
            'generated_at': datetime.now(timezone.utc).isoformat()}
