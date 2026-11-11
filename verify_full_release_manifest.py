"""Verify the SHA-256 manifest for the complete LibraAI distribution ZIP."""
from __future__ import annotations
import hashlib
import re
import sys
import zipfile
from pathlib import PurePosixPath

MANIFEST = 'RELEASE_MANIFEST_FULL.sha256'
HEX = re.compile(r'^[0-9a-f]{64}$')

def verify(path: str) -> dict:
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            names = [i.filename for i in infos]
            if len(names) != len(set(names)):
                return {'valid': False, 'issues': ['duplicate_archive_member']}
            if names.count(MANIFEST) != 1:
                return {'valid': False, 'issues': ['manifest_missing_or_duplicated']}
            raw = z.read(MANIFEST)
            if len(raw) > 32 * 1024 * 1024:
                return {'valid': False, 'issues': ['manifest_too_large']}
            expected = {}
            for line_no, line in enumerate(raw.decode('utf-8').splitlines(), 1):
                if not line:
                    continue
                parts = line.split('  ', 1)
                if len(parts) != 2 or not HEX.fullmatch(parts[0]):
                    return {'valid': False, 'issues': [f'invalid_manifest_line:{line_no}']}
                name = parts[1]
                p = PurePosixPath(name)
                if ('\\' in name or p.is_absolute() or any(x in ('', '.', '..') for x in p.parts)
                    or name == MANIFEST or name in expected):
                    return {'valid': False, 'issues': [f'unsafe_or_duplicate_manifest_path:{line_no}']}
                expected[name] = parts[0]
            actual = set(names) - {MANIFEST}
            if actual != set(expected):
                return {'valid': False, 'issues': ['archive_members_do_not_match_manifest'],
                        'unlisted': sorted(actual-set(expected))[:20],
                        'missing': sorted(set(expected)-actual)[:20]}
            issues = []
            for name, digest in expected.items():
                h = hashlib.sha256()
                with z.open(name) as f:
                    for chunk in iter(lambda: f.read(1024*1024), b''):
                        h.update(chunk)
                if h.hexdigest() != digest:
                    issues.append('hash_mismatch:'+name)
            bad = z.testzip()
            if bad:
                issues.append('zip_crc_failure:'+bad)
            return {'valid': not issues, 'issues': issues,
                    'checked_files': len(expected), 'listed_files': len(expected)}
    except (OSError, UnicodeDecodeError, ValueError, zipfile.BadZipFile, RuntimeError, EOFError) as exc:
        return {'valid': False, 'issues': ['invalid_or_corrupt_archive'], 'detail': type(exc).__name__}

if __name__ == '__main__':
    result = verify(sys.argv[1]) if len(sys.argv) == 2 else {'valid': False, 'issues': ['usage: python verify_full_release_manifest.py release.zip']}
    import json
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result.get('valid') else 1)
