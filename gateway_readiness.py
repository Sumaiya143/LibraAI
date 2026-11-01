"""Offline, read-only payment gateway deployment configuration preflight.

Does not contact providers or print secrets. Not a substitute for live transactions.
"""
import argparse
import json
import os
import ipaddress
from urllib.parse import urlsplit

PROVIDERS = {
    'sslcommerz': ('SSLCOMMERZ_STORE_ID', 'SSLCOMMERZ_STORE_PASSWORD'),
    'bkash': ('BKASH_USERNAME', 'BKASH_PASSWORD', 'BKASH_APP_KEY', 'BKASH_APP_SECRET'),
}

def _public_hostname(host):
    """Reject local, private, reserved, and non-DNS callback destinations."""
    if not host or host.endswith('.') or '.' not in host:
        return False
    host = host.lower()
    if host.endswith(('.localhost', '.local', '.internal', '.test', '.invalid')):
        return False
    try:
        ipaddress.ip_address(host)
        return False  # Require a DNS hostname; avoid private and literal IP origins.
    except ValueError:
        pass
    labels = host.split('.')
    return all(0 < len(label) <= 63 and label[0].isalnum() and label[-1].isalnum()
               and all(c.isascii() and (c.isalnum() or c == '-') for c in label)
               for label in labels) and len(host) <= 253


def inspect_config(env=None, production=None):
    env = dict(os.environ if env is None else env)
    production = (env.get('LIBRAAI_ENV', '').lower() == 'production') if production is None else production
    checks = []
    def add(code, ok, detail):
        checks.append({'code': code, 'passed': bool(ok), 'detail': detail})
    secret = env.get('SECRET_KEY', '')
    add('session_secret', len(secret) >= 32 and secret.strip() == secret and len(set(secret)) >= 8,
        'Set a unique, high-entropy SECRET_KEY (at least 32 characters).')
    canonical_url = env.get('LIBRAAI_PUBLIC_URL', '').strip()
    legacy_url = env.get('PUBLIC_BASE_URL', '').strip()
    url = canonical_url or legacy_url
    add('public_url_consistent', not (canonical_url and legacy_url) or canonical_url.rstrip('/') == legacy_url.rstrip('/'),
        'LIBRAAI_PUBLIC_URL and legacy PUBLIC_BASE_URL must match when both are set.')
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        parsed = urlsplit('')
        port = None
    valid_url = (parsed.scheme == 'https' and _public_hostname(parsed.hostname) and not parsed.username
                 and not parsed.password and not parsed.query and not parsed.fragment
                 and parsed.path in ('', '/') and port in (None, 443))
    add('public_https_url', valid_url, 'Set LIBRAAI_PUBLIC_URL to the public HTTPS origin; legacy PUBLIC_BASE_URL is accepted as an alias.')
    for provider, required in PROVIDERS.items():
        present = all(bool(env.get(k, '').strip()) for k in required)
        add(provider + '_credentials', present, 'Configure all required ' + provider + ' merchant credentials.')
        sandbox = env.get(provider.upper() + '_SANDBOX', 'true').lower()
        add(provider + '_mode', sandbox in ('true', 'false') and (not production or sandbox == 'false'),
            'Production requires explicitly setting ' + provider.upper() + '_SANDBOX=false.')
    return {'environment': 'production' if production else 'non-production',
            'ready': all(c['passed'] for c in checks), 'checks': checks,
            'note': 'Offline configuration checks only; no payment, refund, or network verification performed.'}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production', action='store_true', help='Require production gateway settings')
    args = parser.parse_args(argv)
    result = inspect_config(production=True if args.production else None)
    print(json.dumps(result, indent=2))
    return 0 if result['ready'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
