"""Fail-closed, offline release gate combining configuration and package checks.

This is NOT certification, nor a live payment or penetration test.
"""
import argparse
import json
from pathlib import Path
from gateway_readiness import inspect_config

REQUIRED_FILES = ('app.py', 'payment_engine.py', 'payment_routes.py',
                  'refund_engine.py', 'digital_entitlements.py',
                  'backup_restore_drill.py', 'requirements.txt')


def release_gate(root=None, env=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parent
    config = inspect_config(env=env, production=True)
    files = [{'name': name, 'present': (root / name).is_file()}
             for name in REQUIRED_FILES]
    # Audit every entry (including links to directories) without traversing symlinks.
    # Avoid returning file contents or credential values in reports.
    from buyer_preflight import BLOCKED_NAMES, BLOCKED_EXTENSIONS, DEVELOPMENT_PARTS
    forbidden = []
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if path.is_symlink():
            forbidden.append(relative.as_posix())
            continue
        if any(part in DEVELOPMENT_PARTS for part in relative.parts):
            forbidden.append(relative.as_posix())
            continue
        if not path.is_file():
            continue
        lower = path.name.lower()
        if (lower in BLOCKED_NAMES or path.suffix.lower() in BLOCKED_EXTENSIONS
                or lower.startswith('.env.') or lower == '.env'
                or lower in {'credentials.json', 'service-account.json',
                             'id_rsa', 'id_ed25519'}):
            forbidden.append(relative.as_posix())
    forbidden = sorted(set(forbidden))
    # A symlink must never satisfy the presence check for a required source file.
    for entry in files:
        if (root / entry['name']).is_symlink():
            entry['present'] = False
    return {'ready_for_release_review': bool(config['ready'] and all(f['present'] for f in files)
                                             and not forbidden),
            'gateway_configuration': config, 'required_source_files': files,
            'prohibited_package_files': forbidden,
            'remaining_external_checks': ['live payment and refund transactions',
                 'end-to-end checkout and fulfillment', 'production deployment and restore rehearsal',
                 'independent security assessment', 'buyer acceptance testing'],
            'note': 'Offline checks only. This is not a production certificate.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=str(Path(__file__).resolve().parent))
    args = parser.parse_args(argv)
    result = release_gate(args.root)
    print(json.dumps(result, indent=2))
    return 0 if result['ready_for_release_review'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
