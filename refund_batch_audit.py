"""Read-only full-database refund audit with bounded paging and deterministic summaries."""
import argparse
import json
import sqlite3
from pathlib import Path
from refund_integrity_audit import audit_refunds
from refund_csv_export import export_refund_issues


def audit_all_refunds(conn, page_size=500, max_records=100000, exceptions_only=False):
    if type(page_size) is not int or not 1 <= page_size <= 500:
        raise ValueError('page_size must be 1..500')
    if type(max_records) is not int or not 1 <= max_records <= 100000:
        raise ValueError('max_records must be 1..100000')
    checked = 0
    offset = 0
    issues = []
    issue_types = {}
    while checked < max_records:
        page = audit_refunds(conn, min(page_size, max_records - checked), offset)
        checked += page['checked']
        offset += page['checked']
        for item in page['issues']:
            issues.append(item)
            for problem in item['issues']:
                issue_types[problem] = issue_types.get(problem, 0) + 1
        if not page['has_more'] or not page['checked']:
            break
    truncated = bool(page['has_more']) if checked else False
    result = {'checked': checked, 'issue_count': len(issues),
              'issue_types': dict(sorted(issue_types.items())),
              'truncated': truncated, 'read_only': True}
    if not exceptions_only:
        result['issues'] = issues
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only paginated refund audit')
    parser.add_argument('--db', required=True)
    parser.add_argument('--page-size', type=int, default=500)
    parser.add_argument('--max-records', type=int, default=100000)
    parser.add_argument('--summary-only', action='store_true')
    parser.add_argument('--csv-report', help='Create new spreadsheet-safe CSV of anomalies (never overwrite)')
    args = parser.parse_args(argv)
    path = Path(args.db)
    if not path.is_file():
        parser.error('Database file does not exist')
    if not 1 <= args.page_size <= 500 or not 1 <= args.max_records <= 100000:
        parser.error('page-size must be 1..500 and max-records must be 1..100000')
    with sqlite3.connect('file:' + path.resolve().as_posix() + '?mode=ro', uri=True) as conn:
        result = audit_all_refunds(conn, args.page_size, args.max_records, args.summary_only and not args.csv_report)
    if args.csv_report:
        try:
            export_refund_issues(result, args.csv_report)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
    if args.summary_only:
        result.pop('issues', None)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 2 if result['issue_count'] or result['truncated'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
