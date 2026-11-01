"""Read-only, bounded full-range payment integrity reconciliation."""
import argparse
import collections
import json
import pathlib
import sqlite3
from payment_integrity_audit import audit
from payment_csv_export import export_payment_issues


def scan(conn, page_size=250, max_records=100000, include_anomalies=True):
    if type(page_size) is not int or not 1 <= page_size <= 5000:
        raise ValueError('page_size must be between 1 and 5000')
    if type(max_records) is not int or not 1 <= max_records <= 1000000:
        raise ValueError('max_records must be between 1 and 1000000')
    # Stable snapshot ensures pages cannot drift during concurrent writes.
    conn.execute('BEGIN')
    try:
        offset = 0
        counts = collections.Counter()
        findings = []
        while offset < max_records:
            page = audit(conn, min(page_size, max_records-offset), offset)
            for finding in page['anomalies']:
                counts.update(finding['issues'])
                if include_anomalies:
                    findings.append(finding)
            offset += page['checked']
            if not page['has_more']:
                break
        else:
            # A separate probe distinguishes an exactly-full scan from a truncated one.
            page = audit(conn, 1, offset)
            if page['checked']:
                return _report(offset, counts, findings, True)
        return _report(offset, counts, findings, False)
    finally:
        conn.rollback()  # Ends read snapshot without modifying records.


def _report(checked, counts, findings, incomplete):
    return {'checked': checked, 'anomaly_counts': dict(sorted(counts.items())),
            'anomaly_total': sum(counts.values()), 'incomplete': incomplete,
            'anomalies': findings}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only paginated payment integrity audit')
    parser.add_argument('--db', required=True)
    parser.add_argument('--page-size', type=int, default=250)
    parser.add_argument('--max-records', type=int, default=100000)
    parser.add_argument('--summary-only', action='store_true')
    parser.add_argument('--csv-report', help='Create a new CSV of anomalies; never overwrite')
    args = parser.parse_args(argv)
    uri = pathlib.Path(args.db).resolve().as_uri() + '?mode=ro'
    conn = sqlite3.connect(uri, uri=True)
    try:
        result = scan(conn, args.page_size, args.max_records, not args.summary_only or bool(args.csv_report))
        if args.csv_report:
            try:
                export_payment_issues(result, args.csv_report)
            except (OSError, ValueError) as exc:
                parser.error(str(exc))
        if args.summary_only:
            result['anomalies'] = []
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result['anomaly_total'] or result['incomplete'] else 0
    finally:
        conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
