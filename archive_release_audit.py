"""Inspect a buyer handoff ZIP without extracting it. Offline security check, not certification."""
import argparse
import json
import re
import stat
import zipfile
import unicodedata
from pathlib import PurePosixPath

MAX_FILES = 2000
MAX_TOTAL_BYTES = 250 * 1024 * 1024
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_RATIO = 200
SCAN_CHUNK_BYTES = 64 * 1024
SCAN_OVERLAP_BYTES = 512
WINDOWS_RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{i}' for i in range(1, 10)),
    *(f'LPT{i}' for i in range(1, 10)),
}
TEXT_SUFFIXES = {
    '.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.yaml', '.yml', '.toml',
    '.ini', '.cfg', '.conf', '.env', '.md', '.txt', '.html', '.css', '.sh',
    '.bat', '.ps1', '.sql', '.xml', '.properties', '.lock',
}
# High-confidence credential signatures. This is a heuristic scanner, not DLP.
SECRET_PATTERNS = (
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
    re.compile(r'\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b'),
    re.compile(r'\bgithub_pat_[A-Za-z0-9_]{40,}\b'),
    re.compile(r'\bsk_live_[A-Za-z0-9]{16,}\b'),
    re.compile(r'\bsk-proj-[A-Za-z0-9_-]{30,}\b'),
    re.compile(r'\bAIza[0-9A-Za-z_-]{30,}\b'),
    re.compile(r'\bxox[baprs]-[A-Za-z0-9-]{20,}\b'),
)


def _is_scannable_text(name):
    suffix = PurePosixPath(name).suffix.lower()
    leaf = PurePosixPath(name).name.lower()
    return suffix in TEXT_SUFFIXES or leaf.startswith('.env')


def _stream_contains_high_confidence_secret(name, stream):
    """Scan an eligible text entry incrementally without loading it into memory.

    A short overlap between chunks lets ASCII credential signatures span read
    boundaries. The whole entry is inspected; memory use stays bounded.
    """
    if not _is_scannable_text(name):
        # Still consume the entry so ZIP CRC validation happens.
        while stream.read(SCAN_CHUNK_BYTES):
            pass
        return False

    tail = ''
    found = False
    while True:
        chunk = stream.read(SCAN_CHUNK_BYTES)
        if not chunk:
            break
        # The file extension already classified this entry as text. Do not
        # let a NUL byte suppress scanning: a secret can otherwise be hidden
        # behind a binary-looking prefix in an otherwise eligible source file.
        # Continue consuming even after a match so zipfile validates the CRC.
        if not found:
            text = tail + chunk.decode('utf-8', errors='replace')
            if any(pattern.search(text) for pattern in SECRET_PATTERNS):
                found = True
            tail = text[-SCAN_OVERLAP_BYTES:]
    return found


def audit_archive(path):
    problems = []
    seen = set()
    total = 0
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_FILES:
                problems.append('too_many_entries')
            for entry in infos:
                name = getattr(entry, 'orig_filename', entry.filename) or entry.filename
                raw_filename = getattr(entry, 'filename', '')
                normalized = name.rstrip('/')
                segments = normalized.split('/')
                if (not normalized or name.startswith('/') or '\\' in name
                        or any(part in ('', '.', '..') for part in segments)
                        or re.match(r'^[A-Za-z]:', name)
                        or any(ord(c) < 32 or ord(c) == 127 for c in name)):
                    problems.append('unsafe_entry_path')
                    continue
                # Windows treats alternate data streams and several device names
                # specially; trailing dots/spaces and Unicode-normalization
                # differences can also collide when a ZIP is unpacked elsewhere.
                windows_unsafe = any(
                    ':' in part or part.endswith(('.', ' '))
                    or part.split('.', 1)[0].upper() in WINDOWS_RESERVED_NAMES
                    for part in segments
                )
                if windows_unsafe:
                    problems.append('nonportable_entry_path')
                    continue
                key = unicodedata.normalize('NFC', normalized).casefold()
                if key in seen:
                    problems.append('duplicate_entry_path')
                seen.add(key)
                mode = (entry.external_attr >> 16) & 0xffff
                if stat.S_ISLNK(mode):
                    problems.append('symlink_entry')
                if entry.is_dir():
                    continue
                total += entry.file_size
                if entry.file_size > MAX_FILE_BYTES:
                    problems.append('oversized_entry')
                if entry.file_size and (entry.compress_size == 0 or entry.file_size > MAX_RATIO * max(1, entry.compress_size)):
                    problems.append('suspicious_compression_ratio')
                parts = [p.lower() for p in PurePosixPath(normalized).parts]
                leaf = parts[-1]
                secret_name = (
                    leaf in {
                        '.env', '.npmrc', '.pypirc', '.netrc',
                        'id_rsa', 'id_ed25519', 'id_ecdsa', 'id_dsa',
                        'credentials', 'credentials.json', 'credentials.txt',
                        'secrets', 'secrets.json', 'secret.json', 'token.json',
                        'service-account.json', 'application_default_credentials.json',
                        'accesstokens.json',
                    }
                    or leaf.startswith(('credentials.', 'secrets.', 'secret.'))
                    or (leaf.startswith('.env.') and leaf not in {'.env.example', '.env.production.example'})
                    or leaf.endswith(('.db', '.sqlite', '.sqlite3', '.pem', '.key', '.p12', '.pfx', '.tfstate'))
                    or any(part in ('.aws', '.azure', '.terraform') for part in parts)
                    or ('gcloud' in parts and 'application_default_credentials.json' in parts)
                    or '__pycache__' in parts or '.git' in parts
                )
                if secret_name:
                    problems.append('prohibited_entry')
            if total > MAX_TOTAL_BYTES:
                problems.append('archive_uncompressed_size_limit')
            # Verify CRC and decompression, not just central-directory metadata.
            # Content scanning is streaming and covers the whole eligible text entry.
            if not problems:
                for entry in infos:
                    if entry.is_dir():
                        continue
                    with archive.open(entry) as stream:
                        if _stream_contains_high_confidence_secret(entry.filename, stream):
                            problems.append('possible_secret_content')
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError, EOFError, NotImplementedError) as exc:
        problems.append('invalid_or_corrupt_archive')
    return {'safe_for_handoff_review': not problems, 'issues': sorted(set(problems)),
            'note': 'Archive checks do not certify application or deployment security.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive')
    args = parser.parse_args(argv)
    result = audit_archive(args.archive)
    print(json.dumps(result, indent=2))
    return 0 if result['safe_for_handoff_review'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
