"""Offline handover gate; never asserts live-provider or browser verification."""
import argparse
import ast
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent


def build_report():
    checks = {}
    errors = []
    for path in ROOT.rglob('*.py'):
        if any(part in path.parts for part in ('venv', '.venv', '__pycache__')):
            continue
        try:
            ast.parse(path.read_text(encoding='utf-8-sig'))
        except (SyntaxError, UnicodeError) as exc:
            errors.append(f'{path.relative_to(ROOT)}: {exc}')
    checks['python_syntax'] = {'passed': not errors, 'errors': errors[:20]}
    required = [
        'app.py', 'requirements.txt', 'advanced.py', 'advanced_server.py',
        'integrations.py', 'SECURITY_DEPLOYMENT_CHECKLIST.md', 'README_NEXTJS.md',
    ]
    missing = [name for name in required if not (ROOT / name).is_file()]
    checks['source_manifest'] = {'passed': not missing, 'missing': missing}
    checks['flask_available'] = {'passed': importlib.util.find_spec('flask') is not None}
    checks['provider_live_verification'] = {
        'passed': False, 'reason': 'Requires approved credentials and staging transactions'}
    checks['browser_e2e'] = {
        'passed': False, 'reason': 'Requires Flask runtime and supported browser test environment'}
    checks['physical_indoor_navigation'] = {
        'passed': False, 'reason': 'Requires actual floor plans, QR markers and hardware acceptance'}
    checks['security_external_signoff'] = {
        'passed': False, 'reason': 'Requires independent security review'}
    return {
        'status': 'NOT PRODUCTION VERIFIED',
        'checks': checks,
        'required_for_signoff': [name for name, value in checks.items() if not value['passed']],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', help='Optional path to save the JSON report; otherwise print only.')
    args = parser.parse_args(argv)
    report = build_report()
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        pathlib.Path(args.output).write_text(rendered, encoding='utf-8')
    print(rendered, end='')
    return 0 if all(check['passed'] for check in report['checks'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
