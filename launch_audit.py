"""Offline, read-only launch audit. Never interprets environment flags as proof of certification."""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def audit(env=None, root=ROOT):
    env = os.environ if env is None else env
    root = Path(root)
    checks = []
    def add(code, ok, reason, category='blocker'):
        checks.append({'id': code, 'passed': bool(ok), 'severity': category, 'detail': reason})
    add('https', env.get('LIBRA_HTTPS') == '1' and env.get('PUBLIC_BASE_URL', '').startswith('https://'), 'Configure a real TLS-terminating proxy and an HTTPS public URL; verify certificates separately.')
    add('auth_throttle', env.get('LIBRAAI_AUTH_THROTTLE', '1') == '1', 'Keep login/signup throttling enabled; add shared edge rate limits when using multiple workers.')
    add('gateway_sslcommerz', bool(env.get('SSLCZ_STORE_ID') and env.get('SSLCZ_STORE_PASSWORD')), 'SSLCommerz merchant credentials are missing; presence alone does not establish successful sandbox/live verification.')
    add('gateway_bkash', bool(env.get('BKASH_APP_KEY') and env.get('BKASH_APP_SECRET') and env.get('BKASH_USERNAME') and env.get('BKASH_PASSWORD')), 'bKash merchant credentials are missing; check actual expected variable names in commerce_extra.py.')
    add('payment_e2e', False, 'Requires witnessed sandbox payment, server-to-server verification, refunds, replay and reconciliation tests.')
    add('recurring_billing', False, 'Invoice tracking is not automated recurring collection; requires a provider mandate and renewal webhooks.')
    add('merchant_payout', False, 'Manual payout reconciliation is not automated merchant settlement.')
    add('production_server', False, 'ThreadingHTTPServer is development-grade; deploy through an audited production adapter.')
    add('backup_drill', env.get('LIBRA_BACKUP_VERIFIED') == '1', 'Restore a fresh backup into a separate database and document results; environment flag is only an operator assertion.')
    add('security_audit', False, 'Independent penetration test and security review have not been supplied.')
    add('ai_rag', False, 'End-to-end grounded AI/RAG evaluation, permissions and cost controls are not verified.')
    add('ui_approval', False, 'Screenshot comparison, responsive QA, and user acceptance sign-off not supplied.')
    return {'product': 'LibraAI', 'production_ready': all(x['passed'] for x in checks), 'passed': sum(x['passed'] for x in checks), 'total': len(checks), 'checks': checks, 'notice': 'Credential presence and operator flags do not constitute production certification.'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Offline launch blocker report; no external services contacted')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    result = audit()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for item in result['checks']:
            print(('PASS' if item['passed'] else 'BLOCK') + ' | ' + item['id'] + ' | ' + item['detail'])
        print(f"Production ready: {result['production_ready']} ({result['passed']}/{result['total']} checks)")
    sys.exit(0 if result['production_ready'] else 1)
