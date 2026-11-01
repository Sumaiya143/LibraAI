"""Create and verify a privacy-minimal integrity manifest for reconciliation CSV reports."""
from __future__ import annotations
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import tempfile

SCHEMA = 'libraai-payment-reconciliation-manifest-v1'
EXPECTED_HEADER = b'\xef\xbb\xbfattempt_id,order_id,issue\r\n'
HEX64 = re.compile(r'^[0-9a-f]{64}$')
DEFAULT_HMAC_ENV = 'LIBRAAI_REPORT_HMAC_KEY'

def _hmac_key(env_name: str) -> bytes:
    value = os.environ.get(env_name, '')
    key = value.encode('utf-8')
    if len(key) < 32:
        raise ValueError(f'HMAC key environment variable {env_name} must contain at least 32 UTF-8 bytes')
    return key

def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key in manifest: {key}')
        result[key] = value
    return result

def _canonical(data: dict) -> bytes:
    unsigned = {k: v for k, v in data.items() if k != 'hmac_sha256'}
    return json.dumps(unsigned, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def _digest(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def _safe_csv(path: Path) -> None:
    if path.suffix.lower() != '.csv' or not path.is_file() or path.is_symlink():
        raise ValueError('A regular, non-symlink CSV file is required')
    with path.open('rb') as stream:
        if stream.readline() != EXPECTED_HEADER:
            raise ValueError('Unexpected reconciliation CSV header')


def create_manifest(csv_path, manifest_path, hmac_key_env=None):
    csv_file = Path(csv_path)
    manifest_file = Path(manifest_path)
    _safe_csv(csv_file)
    if manifest_file.suffix.lower() != '.json':
        raise ValueError('Manifest destination must use .json extension')
    if manifest_file.resolve(strict=False) == csv_file.resolve(strict=False):
        raise ValueError('CSV and manifest destinations must differ')
    digest, size = _digest(csv_file)
    data = {
        'schema': SCHEMA,
        'file_name': csv_file.name,
        'sha256': digest,
        'size_bytes': size,
        'header': ['attempt_id', 'order_id', 'issue'],
        'note': 'SHA-256 checks file integrity. HMAC authenticates only when configured and verified with a trusted secret.'
    }
    if hmac_key_env:
        key = _hmac_key(hmac_key_env)
        data['hmac_algorithm'] = 'HMAC-SHA256'
        data['hmac_sha256'] = hmac.new(key, _canonical(data), hashlib.sha256).hexdigest()
    # Exclusive create: never silently replace a previously issued manifest.
    payload = (json.dumps(data, sort_keys=True, indent=2) + '\n').encode('utf-8')
    fd = os.open(manifest_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            manifest_file.unlink()
        except OSError:
            pass
        raise
    return data


def verify_manifest(csv_path, manifest_path, hmac_key_env=None):
    csv_file = Path(csv_path)
    manifest_file = Path(manifest_path)
    _safe_csv(csv_file)
    if not manifest_file.is_file() or manifest_file.is_symlink():
        raise ValueError('A regular, non-symlink manifest file is required')
    try:
        data = json.loads(manifest_file.read_text(encoding='utf-8'), object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError('Invalid manifest JSON') from exc
    if not isinstance(data, dict) or data.get('schema') != SCHEMA:
        raise ValueError('Unsupported manifest schema')
    signature = data.get('hmac_sha256')
    authenticated = False
    if signature is not None:
        if data.get('hmac_algorithm') != 'HMAC-SHA256' or not isinstance(signature, str) or not HEX64.fullmatch(signature):
            raise ValueError('Invalid HMAC metadata')
        if not hmac_key_env:
            raise ValueError('Signed manifest requires --hmac-key-env for authentication')
        key = _hmac_key(hmac_key_env)
        expected_hmac = hmac.new(key, _canonical(data), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_hmac):
            raise ValueError('Manifest HMAC authentication failed')
        authenticated = True
    elif hmac_key_env:
        raise ValueError('HMAC key supplied but manifest is unsigned')
    if data.get('file_name') != csv_file.name:
        raise ValueError('CSV filename does not match manifest')
    if type(data.get('size_bytes')) is not int or data['size_bytes'] < 0:
        raise ValueError('Invalid manifest size')
    if not isinstance(data.get('sha256'), str) or not HEX64.fullmatch(data['sha256']):
        raise ValueError('Invalid manifest checksum')
    digest, size = _digest(csv_file)
    return {'valid': size == data['size_bytes'] and digest == data['sha256'],
            'authenticated': authenticated,
            'expected_sha256': data['sha256'], 'actual_sha256': digest,
            'expected_size_bytes': data['size_bytes'], 'actual_size_bytes': size}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create')
    create.add_argument('--csv', required=True)
    create.add_argument('--manifest', required=True)
    create.add_argument('--hmac-key-env', help=f'environment variable holding HMAC key (default name: {DEFAULT_HMAC_ENV})')
    verify = sub.add_parser('verify')
    verify.add_argument('--csv', required=True)
    verify.add_argument('--manifest', required=True)
    verify.add_argument('--hmac-key-env', help=f'environment variable holding HMAC key (default name: {DEFAULT_HMAC_ENV})')
    args = parser.parse_args(argv)
    try:
        result = create_manifest(args.csv, args.manifest, args.hmac_key_env) if args.command == 'create' else verify_manifest(args.csv, args.manifest, args.hmac_key_env)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0 if args.command == 'create' or result['valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
