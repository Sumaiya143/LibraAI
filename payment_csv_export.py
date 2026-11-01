"""Minimal, spreadsheet-safe export of payment reconciliation exceptions."""
import csv
from pathlib import Path

FIELDS = ('attempt_id', 'order_id', 'issue')


def _cell(value):
    if type(value) is not int or value < 0:
        raise ValueError('Invalid numeric audit identifier')
    return str(value)


def export_payment_issues(report, destination):
    """Create an exclusive CSV; never overwrite existing reports or follow symlinks."""
    if not isinstance(report, dict) or not isinstance(report.get('anomalies'), list):
        raise ValueError('Full anomaly report required for CSV export')
    rows = []
    for anomaly in report['anomalies']:
        if not isinstance(anomaly, dict) or not isinstance(anomaly.get('issues'), list):
            raise ValueError('Invalid audit anomaly')
        attempt = _cell(anomaly.get('attempt_id'))
        order = _cell(anomaly.get('order_id'))
        for issue in anomaly['issues']:
            if not isinstance(issue, str) or not issue or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_' for c in issue):
                raise ValueError('Invalid issue code')
            rows.append((attempt, order, issue))
    path = Path(destination)
    if path.suffix.lower() != '.csv':
        raise ValueError('CSV report must have .csv extension')
    # x mode atomically refuses existing paths, including symbolic links.
    with path.open('x', encoding='utf-8-sig', newline='') as out:
        writer = csv.writer(out)
        writer.writerow(FIELDS)
        writer.writerows(rows)
    return len(rows)
