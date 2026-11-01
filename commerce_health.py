"""Read-only operational gate for commerce database anomalies.

Exit status: 0 = no findings; 2 = detected anomaly; 3 = incomplete schema.
This is not a substitute for settlement confirmation or an independent audit.
"""
import argparse
import json
import sqlite3
from pathlib import Path
from commerce_reconciliation import report
from payout_health import findings as payout_findings


def assess(conn):
    summary = report(conn)
    findings = []
    for warning in summary['warnings']:
        findings.append({'code': 'MISSING_TABLE', 'severity': 'unknown', 'detail': warning})
    overdue = summary.get('overdue_unpaid_invoices')
    if overdue is None and not any('subscription_invoices' in w for w in summary['warnings']):
        findings.append({'code': 'MISSING_EXPIRY_COLUMN', 'severity': 'unknown'})
    elif overdue is not None and overdue > 0:
        findings.append({'code': 'OVERDUE_INVOICES', 'severity': 'warning', 'count': overdue})
    duplicates = summary.get('duplicate_bkash_transaction_ids')
    if duplicates is None and not any('bkash_attempts' in w for w in summary['warnings']):
        findings.append({'code': 'MISSING_TRANSACTION_COLUMN', 'severity': 'unknown'})
    elif duplicates is not None and duplicates > 0:
        findings.append({'code': 'DUPLICATE_TRANSACTION_IDS', 'severity': 'critical', 'count': duplicates})
    findings.extend(payout_findings(conn))
    return {
        'status': 'incomplete' if any(f['severity'] == 'unknown' for f in findings) else ('attention_required' if findings else 'no_detected_anomalies'),
        'findings': findings,
        'summary': summary,
        'disclaimer': 'Local database diagnostics only; provider settlement and actual bank payouts are not verified.'
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only commerce health gate')
    parser.add_argument('--database', help='Existing SQLite database; defaults to application database')
    args = parser.parse_args(argv)
    if args.database:
        path = Path(args.database)
    else:
        from server import DB
        path = Path(DB)
    if not path.is_file():
        parser.error('Database does not exist; initialize application first')
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as conn:
        result = assess(conn)
    print(json.dumps(result, indent=2, sort_keys=True))
    return {'no_detected_anomalies': 0, 'attention_required': 2, 'incomplete': 3}[result['status']]


if __name__ == '__main__':
    raise SystemExit(main())
