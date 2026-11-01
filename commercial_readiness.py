"""Fail-closed preflight for real-money launch. No provider calls or secret disclosure."""
import os
from pathlib import Path
from urllib.parse import urlsplit
import ipaddress

REQUIRED = ('SECRET_KEY', 'LIBRAAI_PUBLIC_URL', 'SSLCOMMERZ_STORE_ID',
            'SSLCOMMERZ_STORE_PASSWORD', 'BKASH_APP_KEY', 'BKASH_APP_SECRET',
            'BKASH_USERNAME', 'BKASH_PASSWORD')

def valid_public_origin(value):
    """Use the payment callback validator so launch gates cannot drift apart."""
    try:
        from payment_origin import validate_public_origin
        from payment_providers import GatewayError
        validate_public_origin(value)
        return True
    except (GatewayError, ValueError, TypeError):
        return False

def inspect(env=None, root=None):
    env = os.environ if env is None else env
    root = Path(__file__).parent if root is None else Path(root)
    issues = []
    if env.get('LIBRAAI_ENV') != 'production':
        issues.append('LIBRAAI_ENV must be production')
    if len(env.get('SECRET_KEY', '')) < 32 or 'REPLACE' in env.get('SECRET_KEY','').upper():
        issues.append('Strong SECRET_KEY missing')
    origin = env.get('LIBRAAI_PUBLIC_URL','')
    if not valid_public_origin(origin):
        issues.append('Public URL must be a valid HTTPS origin')
    for name in REQUIRED[2:]:
        value = env.get(name, '')
        if not value or value.lower().startswith(('replace','your_','test_')):
            issues.append(name + ' not configured')
    storefront = (root / 'app.py').read_text(encoding='utf8') if (root / 'app.py').exists() else ''
    if 'Bookstore & marketplace' in storefront and '<p>${{b[' in storefront:
        issues.append('USD storefront incompatible with BDT payment')
    # A code-level currency label is not proof that existing database prices are BDT.
    import sqlite3
    database = env.get('LIBRAAI_DB_PATH', str(root / 'libraai.db'))
    if not Path(database).is_file():
        issues.append('Database missing; BDT price migration not verified')
    else:
        try:
            with sqlite3.connect(database) as conn:
                row = conn.execute("SELECT value FROM commercial_metadata WHERE key='catalog_currency'").fetchone()
                if not row or row[0] != 'BDT':
                    issues.append('Catalog currency not verified as BDT')
        except sqlite3.Error:
            issues.append('Catalog BDT migration metadata missing')
    if env.get('LIBRAAI_LIVE_PAYMENT_E2E_VERIFIED') != 'yes':
        issues.append('Live gateway E2E verification not attested')
    if env.get('LIBRAAI_LICENSE_RIGHTS_VERIFIED') != 'yes':
        issues.append('Content distribution rights not attested')
    if env.get('LIBRAAI_SECURITY_REVIEW_PASSED') != 'yes':
        issues.append('Independent security review not attested')
    return {'ready': not issues, 'issues': issues}

if __name__ == '__main__':
    import json, sys
    result = inspect()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['ready'] else 1)
