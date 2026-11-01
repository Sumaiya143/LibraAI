"""Read-only payout ledger diagnostics; never confirms external disbursement."""
from decimal import Decimal, InvalidOperation


def findings(conn):
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'merchant_payouts' not in tables:
        return []  # Missing tables are reported by the general commerce health gate.
    cols = {row[1] for row in conn.execute('PRAGMA table_info(merchant_payouts)')}
    if not {'id', 'amount', 'currency', 'status'}.issubset(cols):
        return []  # Older/minimal schemas are covered by general migration checks.
    result = []
    invalid = 0
    for amount, currency in conn.execute('SELECT amount,currency FROM merchant_payouts'):
        try:
            money = Decimal(str(amount))
            if not money.is_finite() or money <= 0 or money.as_tuple().exponent < -2 or currency != 'BDT':
                invalid += 1
        except (InvalidOperation, ValueError, TypeError):
            invalid += 1
    if invalid:
        result.append({'code': 'INVALID_PAYOUT_AMOUNT_OR_CURRENCY', 'severity': 'critical', 'count': invalid})
    if 'payout_review_events' in tables:
        event_cols = {row[1] for row in conn.execute('PRAGMA table_info(payout_review_events)')}
        if {'payout_id', 'new_status', 'reference'}.issubset(event_cols):
            missing = conn.execute('''SELECT COUNT(*) FROM merchant_payouts p
                WHERE p.status='paid' AND NOT EXISTS
                (SELECT 1 FROM payout_review_events e WHERE e.payout_id=p.id
                 AND e.new_status='paid' AND e.reference IS NOT NULL AND trim(e.reference) != '')''').fetchone()[0]
            if missing:
                result.append({'code': 'PAID_PAYOUT_WITHOUT_REFERENCE_EVENT', 'severity': 'critical', 'count': missing})
            reused = conn.execute('''SELECT COUNT(*) FROM (
                SELECT reference FROM payout_review_events
                WHERE new_status='paid' AND reference IS NOT NULL AND trim(reference) != ''
                GROUP BY reference HAVING COUNT(DISTINCT payout_id)>1)''').fetchone()[0]
            if reused:
                result.append({'code': 'REUSED_PAYOUT_REFERENCE', 'severity': 'critical', 'count': reused})
    return result
