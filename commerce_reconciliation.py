"""Read-only operational reconciliation report; does not move funds or grant access."""
import argparse
import json
import sqlite3
from pathlib import Path


def report(conn):
    """Return aggregated status counts and anomalies without customer identifiers."""
    def exists(table):
        return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None
    output = {'invoices': {}, 'bkash_attempts': {}, 'orders': {}, 'payouts': {}, 'warnings': []}
    for table, key in [('subscription_invoices','invoices'),('bkash_attempts','bkash_attempts'),('orders','orders'),('merchant_payouts','payouts')]:
        if not exists(table):
            output['warnings'].append(table + ' table not initialized')
            continue
        for status, count in conn.execute('SELECT status, COUNT(*) FROM "'+table+'" GROUP BY status'):
            output[key][str(status)] = count
    if exists('subscription_invoices'):
        output['overdue_unpaid_invoices'] = conn.execute("SELECT COUNT(*) FROM subscription_invoices WHERE status='unpaid' AND expires_at IS NOT NULL AND expires_at <= datetime('now')").fetchone()[0] if 'expires_at' in {r[1] for r in conn.execute('PRAGMA table_info(subscription_invoices)')} else None
    if exists('bkash_attempts'):
        output['duplicate_bkash_transaction_ids'] = conn.execute("SELECT COUNT(*) FROM (SELECT trx_id FROM bkash_attempts WHERE trx_id IS NOT NULL GROUP BY trx_id HAVING COUNT(*) > 1)").fetchone()[0] if 'trx_id' in {r[1] for r in conn.execute('PRAGMA table_info(bkash_attempts)')} else None
    output['note'] = 'Read-only diagnostic; not proof of provider settlement or bank transfer.'
    return output


def main():
    parser = argparse.ArgumentParser(description='Read-only LibraAI commerce reconciliation summary')
    parser.add_argument('--database', help='SQLite database path (defaults to LibraAI application database)')
    args = parser.parse_args()
    if args.database:
        path = Path(args.database)
        if not path.is_file():
            parser.error('Database file does not exist')
    else:
        from server import DB
        path = Path(DB)
        if not path.is_file():
            parser.error('Application database does not exist; initialize the app first')
    with sqlite3.connect('file:' + str(path.resolve()) + '?mode=ro', uri=True) as conn:
        print(json.dumps(report(conn), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
