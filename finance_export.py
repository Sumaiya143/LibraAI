"""Offline, read-only BDT payment/refund reconciliation export for authorized operators.

Run locally against a protected database copy. Does not expose customer PII.
"""
import argparse
import csv
import io
import json
import sqlite3
from pathlib import Path

HEADERS = ('order_id', 'order_status', 'order_total_bdt', 'payment_provider',
           'payment_state', 'paid_bdt', 'verified_refunds_bdt',
           'refunds_awaiting_gateway_bdt', 'remaining_paid_bdt', 'review_flag')


def money(cents):
    return f'{cents // 100}.{cents % 100:02d}'


def safe_cell(value):
    """Prevent spreadsheet formula injection in every exported text cell."""
    s = str(value if value is not None else '')
    if s.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
        return "'" + s
    return s


def report(conn):
    conn.row_factory = sqlite3.Row
    rows = conn.execute('''
        SELECT o.id AS order_id, o.status AS order_status,
               CAST(ROUND(o.total * 100) AS INTEGER) AS total_cents,
               p.provider AS provider, p.state AS payment_state,
               p.amount_cents AS payment_cents, p.id AS attempt_id
        FROM orders o LEFT JOIN payment_attempts p
          ON p.id=(SELECT id FROM payment_attempts
                   WHERE order_id=o.id ORDER BY (state='paid') DESC,id DESC LIMIT 1)
        ORDER BY o.id
    ''').fetchall()
    results = []
    for row in rows:
        verified = awaiting = 0
        if row['attempt_id'] is not None:
            refunds = conn.execute('''SELECT state,COALESCE(SUM(amount_cents),0) AS amount
                FROM refund_requests WHERE attempt_id=? GROUP BY state''',
                (row['attempt_id'],)).fetchall()
            by_state = {r['state']: r['amount'] for r in refunds}
            verified = by_state.get('refunded', 0)
            awaiting = by_state.get('requested', 0) + by_state.get('approved', 0)
        paid = row['payment_cents'] if row['payment_state'] == 'paid' else 0
        flags = []
        if paid and row['total_cents'] != paid:
            flags.append('AMOUNT_MISMATCH')
        if verified > paid:
            flags.append('OVER_REFUND')
        if paid and row['order_status'] in ('Cancelled', 'Awaiting payment', 'Awaiting payment — sandbox only'):
            flags.append('PAID_UNFULFILLED_STATUS')
        if not paid and row['order_status'] in ('Paid — fulfillment pending','Processing','Fulfilled','Completed'):
            flags.append('PAID_STATUS_WITHOUT_PAYMENT')
        results.append(dict(zip(HEADERS, (
            row['order_id'], row['order_status'], money(row['total_cents']),
            row['provider'] or '', row['payment_state'] or '', money(paid),
            money(verified), money(awaiting), money(paid - verified), ','.join(flags)
        ))))
    return results


def csv_text(rows):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=HEADERS, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({key: safe_cell(row.get(key, '')) for key in HEADERS})
    return output.getvalue()


def export_database(db_path, destination):
    source = Path(db_path).resolve()
    if not source.is_file():
        raise FileNotFoundError('Database does not exist')
    # Do not resolve the destination before checking it: resolve() follows a
    # final symlink and can turn an apparently harmless export path into an
    # overwrite of an unrelated target. Exclusive creation also prevents
    # clobbering an existing report (or a hard link to another file).
    destination = Path(destination).expanduser().absolute()
    if destination.is_symlink():
        raise ValueError('Symlink export destination is forbidden')
    if source == destination:
        raise ValueError('Export cannot overwrite database')
    if destination.suffix.lower() != '.csv':
        raise ValueError('Financial export destination must have .csv extension')
    with sqlite3.connect(f'file:{source}?mode=ro', uri=True) as conn:
        content = csv_text(report(conn))
    created = False
    try:
        with destination.open('x', encoding='utf-8-sig', newline='') as handle:
            created = True
            handle.write(content)
    except Exception:
        # Remove only a file this call successfully created; never remove a
        # pre-existing path when exclusive creation fails.
        if created:
            try:
                destination.unlink()
            except OSError:
                pass
        raise
    return {'rows': content.count('\n') - 1, 'output': str(destination)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Offline LibraAI BDT financial export; no customer PII')
    parser.add_argument('--db', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(export_database(args.db, args.output)))
