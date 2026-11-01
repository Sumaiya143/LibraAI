"""Offline, dependency-free source handover safety checks (not a security audit)."""
from pathlib import Path
import json
import sys

REQUIRED = ('app.py','requirements.txt','Dockerfile','compose.market.yaml','Caddyfile','.env.example','payment_routes.py','digital_entitlements.py')
BLOCKED_NAMES = {'.env','.env.production','.env.local','id_rsa','id_ed25519', 'credentials.json', 'service-account.json'}
BLOCKED_EXTENSIONS = {'.db','.sqlite','.sqlite3','.pem','.key','.p12','.pfx'}
DEVELOPMENT_PARTS = {'.git','.venv','venv','__pycache__','.pytest_cache','.mypy_cache','node_modules','.next','out','coverage','playwright-report','test-results','.npm'}


def inspect_package(root):
    root = Path(root)
    errors = []
    for name in REQUIRED:
        if not (root / name).is_file() or (root / name).is_symlink():
            errors.append('Missing or linked required file: ' + name)
    for item in root.rglob('*'):
        relative = item.relative_to(root)
        if item.is_symlink():
            errors.append('Symbolic link in release: ' + str(relative))
            continue
        if not item.is_file():
            continue
        if any(part in DEVELOPMENT_PARTS for part in relative.parts):
            errors.append('Development artifact: ' + str(relative))
        if item.name.lower() in BLOCKED_NAMES or item.suffix.lower() in BLOCKED_EXTENSIONS:
            errors.append('Potential secret or customer database: ' + str(relative))
    return errors


if __name__ == '__main__':
    errors = inspect_package(Path(__file__).resolve().parent)
    print(json.dumps({'handover_files_safe': not errors, 'errors': errors}, indent=2))
    sys.exit(bool(errors))
