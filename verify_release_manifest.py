"""Verify a LibraAI release ZIP against its embedded SHA-256 manifest.

This checks file integrity and archive membership without extracting files. It is
not a digital signature and does not establish who created the archive.
"""
import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import PurePosixPath

MANIFEST_NAME = 'LibraAI/RELEASE_MANIFEST.sha256'
CHUNK_SIZE = 64 * 1024
_HEX_SHA256 = re.compile(r'^[0-9a-f]{64}$')


def _hash_member(archive, info):
    digest = hashlib.sha256()
    with archive.open(info, 'r') as stream:
        while True:
            chunk = stream.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verify_release_manifest(archive_path):
    """Return a JSON-serializable verification report for *archive_path*."""
    try:
        with zipfile.ZipFile(archive_path, 'r') as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if len(names) != len(set(names)):
                return {'valid': False, 'issues': ['duplicate_archive_member']}
            if names.count(MANIFEST_NAME) != 1:
                return {'valid': False, 'issues': ['manifest_missing_or_duplicated']}

            manifest_info = next(item for item in infos if item.filename == MANIFEST_NAME)
            # Keep manifest parsing bounded even for a malicious archive.
            if manifest_info.file_size > 16 * 1024 * 1024:
                return {'valid': False, 'issues': ['manifest_too_large']}
            manifest = archive.read(manifest_info).decode('utf-8')
            expected = {}
            for line_number, line in enumerate(manifest.splitlines(), start=1):
                if not line:
                    continue
                parts = line.split('  ', 1)
                if len(parts) != 2 or not _HEX_SHA256.fullmatch(parts[0]):
                    return {'valid': False, 'issues': [f'invalid_manifest_line:{line_number}']}
                member = parts[1]
                path = PurePosixPath(member)
                if (not member.startswith('LibraAI/') or '\\' in member or
                        path.is_absolute() or any(p in ('', '.', '..') for p in path.parts) or
                        member == MANIFEST_NAME or member in expected):
                    return {'valid': False, 'issues': [f'unsafe_or_duplicate_manifest_path:{line_number}']}
                expected[member] = parts[0]

            actual = set(names) - {MANIFEST_NAME}
            listed = set(expected)
            issues = []
            if actual - listed:
                issues.append('unlisted_archive_members')
            if listed - actual:
                issues.append('manifest_members_missing_from_archive')
            if issues:
                return {'valid': False, 'issues': issues,
                        'checked_files': 0, 'listed_files': len(expected)}

            by_name = {item.filename: item for item in infos}
            checked = 0
            for member in sorted(expected):
                if _hash_member(archive, by_name[member]) != expected[member]:
                    issues.append('hash_mismatch:' + member)
                checked += 1
            # Read all entries to ensure their CRC/decompression stream is valid,
            # including the manifest itself.
            bad_member = archive.testzip()
            if bad_member:
                issues.append('zip_crc_failure:' + bad_member)
            return {'valid': not issues, 'issues': issues,
                    'checked_files': checked, 'listed_files': len(expected)}
    except (OSError, UnicodeDecodeError, ValueError, zipfile.BadZipFile,
            RuntimeError, EOFError, NotImplementedError) as exc:
        return {'valid': False, 'issues': ['invalid_or_corrupt_archive'],
                'detail': type(exc).__name__}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', help='Path to LibraAI release ZIP')
    args = parser.parse_args(argv)
    result = verify_release_manifest(args.archive)
    print(json.dumps(result, indent=2))
    return 0 if result.get('valid') else 1


if __name__ == '__main__':
    raise SystemExit(main())
