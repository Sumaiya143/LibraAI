"""Privacy-minimized, spreadsheet-safe export of refund audit exceptions."""
import csv
from pathlib import Path

FIELDS = ('refund_id', 'order_id', 'issue_codes')


def safe_cell(value):
    """Prevent Excel/LibreOffice formula evaluation even with leading whitespace."""
    value = str(value)
    if value.lstrip(' \t\r\n').startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def export_refund_issues(report, destination):
    if not isinstance(report, dict) or not isinstance(report.get('issues'), list):
        raise ValueError('Full refund audit report with issues required')
    path = Path(destination)
    if path.is_symlink():
        raise ValueError('Symlink destination forbidden')
    # Exclusive creation prevents accidentally overwriting an operator's prior report.
    with path.open('x', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for entry in report['issues']:
            if not isinstance(entry, dict) or not isinstance(entry.get('issues'), list):
                raise ValueError('Invalid issue entry')
            writer.writerow({'refund_id': safe_cell(entry.get('refund_id', '')),
                             'order_id': safe_cell(entry.get('order_id', '')),
                             'issue_codes': safe_cell(';'.join(map(str, entry['issues'])))})
    return path
