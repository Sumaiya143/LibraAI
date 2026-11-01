"""Privacy-minimized, spreadsheet-safe CSV serialization of a bounded refund queue page."""
import csv
import io

FIELDS = ('id', 'order_id', 'amount_cents', 'state', 'created', 'updated', 'provider')


def _safe_cell(value):
    value = '' if value is None else str(value)
    # Excel/LibreOffice can evaluate formulas after leading whitespace/control chars.
    if value.lstrip(' \t\r\n\x00').startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')):
        return "'" + value
    return value


def queue_page_csv(report):
    """Export only allowlisted queue fields; never customer PII, reasons or gateway refs."""
    output = io.StringIO(newline='')
    writer = csv.writer(output, lineterminator='\r\n')
    writer.writerow(FIELDS)
    for item in report['items']:
        writer.writerow([_safe_cell(item.get(key)) for key in FIELDS])
    return output.getvalue()
