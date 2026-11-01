"""Operational launch gate. Never substitutes for gateway or security certification."""
import json
import os
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse

from production_preflight import inspect as inspect_commercial


def inspect(env=None):
    env = dict(os.environ if env is None else env)
    base = inspect_commercial(env)
    checks = list(base['checks'])
    def add(name, ok, detail):
        checks.append({'check': name, 'passed': bool(ok), 'detail': detail})
    url = urlparse(env.get('LIBRAAI_PUBLIC_URL', ''))
    add('public_hostname', url.scheme == 'https' and bool(url.hostname) and url.hostname not in ('localhost','127.0.0.1','example.com','your-real-domain.example'), 'Use a real HTTPS hostname with TLS configured')
    add('sslcommerz_credentials', all(env.get(x) for x in ('SSLCOMMERZ_STORE_ID','SSLCOMMERZ_STORE_PASSWORD')), 'Provide merchant SSLCommerz credentials through protected environment variables')
    add('bkash_credentials', all(env.get(x) for x in ('BKASH_USERNAME','BKASH_PASSWORD','BKASH_APP_KEY','BKASH_APP_SECRET')), 'Provide bKash merchant credentials through protected environment variables')
    add('sslcommerz_live_mode', env.get('SSLCOMMERZ_SANDBOX', 'true').lower() == 'false', 'Sandbox must be disabled only after successful verified sandbox testing')
    add('bkash_live_mode', env.get('BKASH_SANDBOX', 'true').lower() == 'false', 'Sandbox must be disabled only after successful verified sandbox testing')
    path = env.get('LIBRAAI_DB_PATH', '')
    database_ok = False
    if path and Path(path).is_file():
        try:
            with sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro', uri=True, timeout=2) as conn:
                database_ok = conn.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        except (sqlite3.Error, OSError):
            pass
    add('database_integrity', database_ok, 'Persistent database must exist and pass SQLite quick_check')
    add('backup_restore_drill', env.get('LIBRAAI_BACKUP_RESTORE_VERIFIED') == 'yes', 'Perform and document a successful restore test; a backup file alone is insufficient')
    add('gateway_e2e_signoff', env.get('LIBRAAI_GATEWAY_E2E_VERIFIED') == 'yes', 'Complete sandbox payments, cancellation, duplicate callbacks and reconciliation with real merchant sandbox credentials')
    add('legal_content_signoff', env.get('LIBRAAI_CONTENT_RIGHTS_VERIFIED') == 'yes', 'Verify licensed catalog titles, territories, and digital delivery rights')
    add('security_review_signoff', env.get('LIBRAAI_SECURITY_REVIEW_VERIFIED') == 'yes', 'Complete independent security assessment and browser end-to-end tests')
    # The original preflight intentionally blocks unverified product capabilities.
    # Human signoff flags do not override those application-level safety checks.
    return {'ready': all(x['passed'] for x in checks), 'checks': checks}

if __name__ == '__main__':
    result = inspect()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['ready'] else 1)
