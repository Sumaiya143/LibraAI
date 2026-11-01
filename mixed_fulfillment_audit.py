"""Read-only buyer operations audit for mixed print/digital orders.

No changes to payments, entitlements, shipments or order statuses are made.
"""
import argparse
import json
import html
import csv
import sqlite3
from pathlib import Path

DIGITAL = frozenset(('ebook', 'e-book', 'digital', 'pdf', 'epub'))
PAID = frozenset(('Paid — fulfillment pending', 'Processing', 'Fulfilled', 'Completed'))

def inspect_order(conn, order_id):
    if type(order_id) is not int or order_id < 1:
        raise ValueError('Invalid order id')
    conn.row_factory = sqlite3.Row
    order = conn.execute('SELECT id,user_id,status,address FROM orders WHERE id=?', (order_id,)).fetchone()
    if order is None:
        raise ValueError('Order not found')
    items = conn.execute('SELECT book_id,format,quantity FROM order_items WHERE order_id=?', (order_id,)).fetchall()
    issues = []
    print_lines = [i for i in items if str(i['format']).strip().lower() == 'print']
    digital_lines = [i for i in items if str(i['format']).strip().lower() in DIGITAL]
    unknown = [str(i['format']) for i in items if str(i['format']).strip().lower() not in DIGITAL | {'print'}]
    if not items: issues.append('order_has_no_items')
    if any(type(i['quantity']) is not int or i['quantity'] <= 0 for i in items):
        issues.append('invalid_item_quantity')
    if unknown: issues.append('unknown_item_format')
    paid_count = conn.execute("SELECT COUNT(*) FROM payment_attempts WHERE order_id=? AND state='paid'", (order_id,)).fetchone()[0]
    paid = paid_count > 0
    if paid_count > 1: issues.append('multiple_paid_payment_attempts_review_required')
    if order['status'] in PAID and not paid: issues.append('paid_status_without_verified_payment')
    if paid and order['status'] not in PAID: issues.append('verified_payment_without_fulfillment_status')
    # Detect premature fulfillment even when an order is not yet paid.
    shipment_rows = conn.execute('SELECT state FROM print_shipments WHERE order_id=?', (order_id,)).fetchall()
    if shipment_rows and not paid:
        issues.append('shipment_without_verified_payment')
    if shipment_rows and not print_lines:
        issues.append('shipment_without_print_items')
    if len(shipment_rows) > 1:
        issues.append('multiple_shipment_records_review_required')
    if any(row['state'] not in ('packing', 'dispatched', 'delivered') for row in shipment_rows):
        issues.append('invalid_shipment_state')
    entitlement_rows = conn.execute('SELECT user_id,book_id FROM digital_entitlements WHERE order_id=?', (order_id,)).fetchall()
    if entitlement_rows and not paid:
        issues.append('digital_access_without_verified_payment')
    digital_books = {item['book_id'] for item in digital_lines}
    if any(row['user_id'] != order['user_id'] or row['book_id'] not in digital_books for row in entitlement_rows):
        issues.append('unexpected_digital_entitlement')
    if len(entitlement_rows) != len({(row['user_id'],row['book_id']) for row in entitlement_rows}):
        issues.append('duplicate_digital_entitlements_review_required')
    if print_lines:
        if not order['address'] or not str(order['address']).strip(): issues.append('print_shipping_address_missing')
        shipment = conn.execute('SELECT state FROM print_shipments WHERE order_id=?', (order_id,)).fetchone()
        if paid and order['status'] in PAID and shipment is None: issues.append('print_shipment_not_started')
        shipment_state = shipment['state'] if shipment else None
    else:
        shipment_state = None
    missing = []
    if paid and order['status'] in PAID:
        for item in digital_lines:
            licensed = conn.execute("SELECT 1 FROM licensed_documents WHERE book_id=? AND access_policy='licensed' LIMIT 1", (item['book_id'],)).fetchone()
            entitled = conn.execute('SELECT 1 FROM digital_entitlements WHERE order_id=? AND user_id=? AND book_id=? LIMIT 1', (order_id, order['user_id'], item['book_id'])).fetchone()
            if not licensed: missing.append({'book_id': item['book_id'], 'reason': 'licensed_document_missing'})
            elif not entitled: missing.append({'book_id': item['book_id'], 'reason': 'entitlement_missing'})
    if missing: issues.append('digital_fulfillment_incomplete')
    return {'order_id': order_id, 'status': order['status'], 'verified_paid': paid,
            'print_line_count': len(print_lines), 'digital_line_count': len(digital_lines),
            'shipment_state': shipment_state, 'digital_exceptions': missing, 'issues': issues,
            'ready': not issues}

def render_html_report(result):
    """Offline, self-contained exception dashboard. No customer PII or credentials."""
    rows = result['orders'] if 'orders' in result else [result]
    body = []
    for row in rows:
        issues = row.get('issues', [])
        issue_text = ', '.join(html.escape(str(issue), quote=True) for issue in issues) or 'None'
        body.append('<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
            html.escape(str(row['order_id']), quote=True),
            'READY' if row['ready'] else 'REVIEW',
            html.escape(str(row['status']), quote=True), issue_text))
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>LibraAI Fulfillment Audit</title><style>body{font:16px system-ui;margin:2rem;"
            "color:#172334;background:#f7f9fc}table{width:100%;border-collapse:collapse;background:white}"
            "th,td{padding:12px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}"
            "th{background:#e9eff8}td:last-child{overflow-wrap:anywhere}</style></head><body>"
            "<h1>LibraAI Fulfillment Audit</h1><p>Read-only snapshot. Review exceptions manually; "
            "this report does not change orders or payments.</p><table><thead><tr>"
            "<th>Order ID</th><th>Result</th><th>Status</th><th>Issues</th></tr></thead><tbody>"
            + ''.join(body) + "</tbody></table></body></html>")

def write_csv_report(result, fileobj):
    """Export a PII-free operations report, protecting spreadsheet consumers."""
    rows = result['orders'] if 'orders' in result else [result]
    writer = csv.writer(fileobj)
    writer.writerow(('order_id', 'result', 'status', 'issue_codes'))
    for row in rows:
        # CSV quoting alone does not prevent spreadsheet formula execution.
        def safe_cell(value):
            value = str(value)
            if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
                return "'" + value
            return value
        writer.writerow((row['order_id'], 'READY' if row['ready'] else 'REVIEW',
                         safe_cell(row['status']), safe_cell(';'.join(map(str, row.get('issues', []))))))

def main(argv=None):
    p = argparse.ArgumentParser(description='Read-only mixed-order fulfillment audit')
    p.add_argument('--db', required=True)
    p.add_argument('--order-id', type=int)
    p.add_argument('--all', action='store_true', help='Audit a bounded page of orders')
    p.add_argument('--limit', type=int, default=100)
    p.add_argument('--offset', type=int, default=0)
    p.add_argument('--exceptions-only', action='store_true')
    p.add_argument('--html-report', help='Write a new offline HTML operations dashboard (will not overwrite)')
    p.add_argument('--csv-report', help='Write a new PII-free CSV exceptions report (will not overwrite)')
    if not argv: argv = None
    args = p.parse_args(argv)
    if args.all == (args.order_id is not None):
        p.error('Choose exactly one of --all or --order-id')
    if not args.all and (args.limit != 100 or args.offset != 0 or args.exceptions_only):
        p.error('Pagination and filtering require --all')
    path = Path(args.db).resolve()
    if not path.is_file(): p.error('Existing database required; no database will be created')
    try:
        with sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True) as conn:
            result = inspect_orders(conn, args.limit, args.offset, args.exceptions_only) if args.all else inspect_order(conn, args.order_id)
        if args.html_report:
            output = Path(args.html_report)
            try:
                with output.open('x', encoding='utf-8') as report_file:
                    report_file.write(render_html_report(result))
            except OSError as exc:
                p.exit(1, f'Cannot create HTML report: {exc}\n')
        if args.csv_report:
            try:
                with Path(args.csv_report).open('x', encoding='utf-8-sig', newline='') as csv_file:
                    write_csv_report(result, csv_file)
            except OSError as exc:
                p.exit(1, f'Cannot create CSV report: {exc}\n')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if (result['exceptions'] == 0 if args.all else result['ready']) else 2
    except (sqlite3.Error, ValueError) as exc:
        p.exit(1, f'Audit failed: {exc}\n')

def inspect_orders(conn, limit=100, offset=0, exceptions_only=False):
    """Audit a bounded page of orders without changing the database."""
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError('limit must be between 1 and 500')
    if type(offset) is not int or offset < 0:
        raise ValueError('offset must be non-negative')
    ids = [r[0] for r in conn.execute(
        'SELECT id FROM orders ORDER BY id LIMIT ? OFFSET ?', (limit, offset)).fetchall()]
    results = [inspect_order(conn, order_id) for order_id in ids]
    exceptions = [r for r in results if not r['ready']]
    return {'scanned': len(results), 'exceptions': len(exceptions),
            'ready': len(results) - len(exceptions), 'limit': limit, 'offset': offset,
            'orders': exceptions if exceptions_only else results}

if __name__ == '__main__':
    raise SystemExit(main())
