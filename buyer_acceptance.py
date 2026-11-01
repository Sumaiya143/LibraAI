"""Isolated, offline buyer acceptance checks. Does not contact payment gateways."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Running the checker must not create artifacts that fail its own package scan.
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent
PUBLIC = ('/', '/discover', '/marketplace', '/login', '/register', '/signup')
PRIVATE = ('/library', '/admin', '/my/orders')


def static_checks(root=ROOT):
    from buyer_preflight import inspect_package
    problems = inspect_package(root)
    for name in ('BUYER_START_HERE_BN.md', 'BUYER_DELIVERY_SCOPE.json', 'compose.market.yaml', 'Caddyfile'):
        if not (Path(root) / name).is_file():
            problems.append('Missing buyer deliverable: ' + name)
    try:
        scope = json.loads((Path(root) / 'BUYER_DELIVERY_SCOPE.json').read_text(encoding='utf-8'))
        if not isinstance(scope, dict):
            problems.append('Buyer scope must be a JSON object')
    except (ValueError, OSError) as exc:
        problems.append('Invalid buyer scope: ' + str(exc))
    return problems


def runtime_checks():
    # The child process gets a disposable DB, not the buyer's real database.
    with tempfile.TemporaryDirectory(prefix='libraai-acceptance-') as tmp:
        env = os.environ.copy()
        env['LIBRAAI_DB_PATH'] = str(Path(tmp) / 'acceptance.sqlite3')
        env['LIBRAAI_ENV'] = 'development'
        env.pop('LIBRAAI_LIVE_PAYMENT_E2E_VERIFIED', None)
        env.pop('LIBRAAI_PUBLIC_URL', None)
        child = r'''
import json
from app import app, init_db
init_db()
app.config.update(TESTING=True)
results={}
with app.test_client() as client:
    for path in ('/', '/discover', '/marketplace', '/login', '/register', '/signup'):
        response=client.get(path, follow_redirects=False)
        results['GET '+path]={'status':response.status_code,'pass':response.status_code==200}
    for path in ('/library', '/admin', '/my/orders'):
        response=client.get(path, follow_redirects=False)
        results['anonymous GET '+path]={'status':response.status_code,'pass':response.status_code in (302,303,401,403)}
print('LIBRAAI_ACCEPTANCE_JSON='+json.dumps(results,sort_keys=True))
'''
        process = subprocess.run([sys.executable, '-c', child], cwd=str(ROOT), env=env,
                                 capture_output=True, text=True, timeout=60)
        prefix = 'LIBRAAI_ACCEPTANCE_JSON='
        lines = [line[len(prefix):] for line in process.stdout.splitlines() if line.startswith(prefix)]
        if process.returncode or not lines:
            message = (process.stderr or process.stdout or 'No runtime result').strip()
            return {'runtime_available': False, 'error': message[-1500:], 'checks': {}}
        return {'runtime_available': True, 'checks': json.loads(lines[-1])}


def report():
    issues = static_checks()
    runtime = runtime_checks()
    passed = not issues and runtime['runtime_available'] and all(
        item['pass'] for item in runtime['checks'].values())
    return {'overall_pass': passed, 'static_pass': not issues,
            'static_issues': issues, 'runtime': runtime,
            'not_tested': ['Real SSLCommerz/bKash payments and refunds',
                           'Publisher licensing and inventory rights',
                           'Live VPS/HTTPS deployment',
                           'Independent security audit']}


if __name__ == '__main__':
    try:
        result = report()
    except subprocess.TimeoutExpired:
        result = {'overall_pass': False, 'error': 'Runtime smoke test timed out'}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result['overall_pass'] else 1)
