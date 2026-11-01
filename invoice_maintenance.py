"""Safe, idempotent invoice expiry maintenance. No payments or entitlements change."""
import argparse
import json
import sqlite3
from subscription_lifecycle import expire_invoices


def expire_due(c, now=None):
    """Expire only overdue unpaid invoices in an atomic transaction."""
    c.execute('BEGIN IMMEDIATE')
    try:
        count = expire_invoices(c, now=now)
        c.commit()
        return count
    except Exception:
        c.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description='Expire overdue unpaid subscription invoices')
    parser.add_argument('--database', help='SQLite database path (default: application database)')
    args = parser.parse_args()
    if args.database:
        conn = sqlite3.connect(args.database)
    else:
        from production import db
        conn = db()
    try:
        print(json.dumps({'expired_invoices': expire_due(conn)}))
    finally:
        conn.close()


if __name__ == '__main__':
    main()
