"""Read-only, redacted launch-evidence report. Never attests external work itself."""
import json
import os
import sqlite3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from commercial_readiness import inspect


def collect(env=None, root=None):
    env = os.environ if env is None else env
    root = Path(__file__).resolve().parent if root is None else Path(root)
    readiness = inspect(env, root)
    db_path = Path(env.get('LIBRAAI_DB_PATH', str(root / 'libraai.db')))
    database = {'exists': db_path.is_file(), 'integrity': 'not_checked'}
    # Immutable SQLite connections ignore uncheckpointed WAL transactions.
    # Refuse a potentially stale snapshot rather than report misleading integrity.
    wal_path = Path(str(db_path) + '-wal')
    if database['exists'] and wal_path.exists():
        database['integrity'] = 'wal_requires_checkpoint'
    elif database['exists']:
        try:
            # Immutable read-only connection: the diagnostic must not mutate live data.
            with sqlite3.connect(db_path.as_uri() + '?mode=ro&immutable=1', uri=True, timeout=2) as conn:
                result = conn.execute('PRAGMA quick_check').fetchone()
                database['integrity'] = 'ok' if result and result[0] == 'ok' else 'failed'
        except (sqlite3.Error, OSError, ValueError):
            database['integrity'] = 'error'
    checks = {
        'merchant_payment_e2e': env.get('LIBRAAI_LIVE_PAYMENT_E2E_VERIFIED') == 'yes',
        'licensed_content_rights': env.get('LIBRAAI_LICENSE_RIGHTS_VERIFIED') == 'yes',
        'independent_security_review': env.get('LIBRAAI_SECURITY_REVIEW_PASSED') == 'yes',
        'database_integrity': database['integrity'] == 'ok',
    }
    # An environment variable is only an operator claim, never independent evidence.
    return {
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'ready_for_launch': bool(readiness['ready'] and all(checks.values())),
        'preflight_issues': readiness['issues'],
        'operator_attestations_not_independently_verified': {k: v for k,v in checks.items() if k != 'database_integrity'},
        'database': database,
        'next_steps': [
            'Obtain written rights for each commercial book',
            'Perform and document real merchant payment and refund tests',
            'Deploy behind HTTPS and verify live endpoints',
            'Obtain an independent security review before real-money launch',
        ],
    }

def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only LibraAI launch evidence (not a live certification)')
    parser.add_argument('--require-ready', action='store_true', help='Exit nonzero unless every readiness check passes')
    args = parser.parse_args(argv)
    report = collect()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.require_ready and not report['ready_for_launch'] else 0

if __name__ == '__main__':
    sys.exit(main())
