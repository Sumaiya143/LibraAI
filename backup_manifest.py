"""Create and verify integrity manifests for offline SQLite backup artifacts.

SHA-256 detects accidental corruption; optional HMAC authenticates against tampering
when the secret key is managed separately from the backup and manifest.
"""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import tempfile

from backup_manager import verify_database

CHUNK = 1024 * 1024


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _key(secret):
    if secret is None:
        return None
    if not isinstance(secret, (bytes, bytearray)) or len(secret) < 32:
        raise ValueError('HMAC key must be at least 32 bytes')
    return bytes(secret)


def _payload(path):
    path = Path(path)
    verify_database(path)
    return {'version': 1, 'filename': path.name, 'size_bytes': path.stat().st_size,
            'sha256': _sha256(path)}


def _canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def create_manifest(backup, manifest, secret=None):
    key = _key(secret)
    backup, manifest = Path(backup), Path(manifest)
    if backup.resolve() == manifest.resolve():
        raise ValueError('Manifest must not overwrite backup')
    if manifest.exists():
        raise FileExistsError('Refusing to overwrite existing manifest')
    payload = _payload(backup)
    if key:
        payload['hmac_sha256'] = hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()
    manifest.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.libraai-manifest-', dir=manifest.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(payload, output, sort_keys=True, indent=2)
            output.write('\n')
        os.chmod(temp, 0o600)
        if manifest.exists() or manifest.is_symlink():
            raise FileExistsError('Refusing to overwrite existing manifest')
        try:
            os.link(temp, manifest)  # atomic no-clobber creation on same filesystem
        except (AttributeError, OSError, PermissionError):
            if manifest.exists() or manifest.is_symlink():
                raise FileExistsError('Refusing to overwrite existing manifest')
            if hasattr(os, 'O_EXCL') and hasattr(os, 'O_CREAT'):
                with open(temp, 'rb') as sf:
                    data = sf.read()
                fd_out = os.open(str(manifest), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o600)
                with open(fd_out, 'wb', closefd=True) as df:
                    df.write(data)
            else:
                shutil.copy2(temp, manifest)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return payload


def verify_manifest(backup, manifest, secret=None, require_hmac=False):
    key = _key(secret)
    if require_hmac and key is None:
        raise ValueError('HMAC verification requires a key')
    with open(manifest, 'r', encoding='utf-8') as source:
        payload = json.load(source)
    if not isinstance(payload, dict):
        raise ValueError('Invalid manifest structure')
    expected_fields = {'version', 'filename', 'size_bytes', 'sha256'}
    if set(payload) not in (expected_fields, expected_fields | {'hmac_sha256'}):
        raise ValueError('Unexpected manifest fields')
    signature = payload.get('hmac_sha256')
    if require_hmac and signature is None:
        raise ValueError('Unsigned manifest rejected')
    if signature is not None and key is None:
        raise ValueError('Signed manifest requires HMAC key')
    unsigned = {k: v for k, v in payload.items() if k != 'hmac_sha256'}
    if signature is not None:
        expected = hmac.new(key, _canonical(unsigned), hashlib.sha256).hexdigest()
        if not isinstance(signature, str) or not hmac.compare_digest(signature, expected):
            raise ValueError('Manifest authentication failed')
    actual = _payload(backup)
    if unsigned != actual:
        raise ValueError('Backup does not match manifest')
    return {'verified': True, 'authenticated': signature is not None,
            'size_bytes': actual['size_bytes']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('create', 'verify'))
    parser.add_argument('--backup', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--hmac-key-env', help='Environment variable holding secret key (minimum 32 UTF-8 bytes)')
    parser.add_argument('--require-hmac', action='store_true')
    args = parser.parse_args()
    key = None
    if args.hmac_key_env:
        value = os.environ.get(args.hmac_key_env)
        if value is None:
            parser.error('HMAC environment variable is not set')
        key = value.encode('utf-8')
    try:
        result = (create_manifest(args.backup, args.manifest, key) if args.action == 'create'
                  else verify_manifest(args.backup, args.manifest, key, args.require_hmac))
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, 'Manifest operation failed: ' + str(exc) + '\n')
