"""Deterministic, fail-closed commercial source archive builder."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo
import shutil
import hashlib
import stat
import sys
import os
import tempfile
from buyer_preflight import REQUIRED as PREFLIGHT_REQUIRED, BLOCKED_EXTENSIONS, BLOCKED_NAMES, DEVELOPMENT_PARTS

EXCLUDE_FILES = {'commercial_release_evidence.json', 'local_verification_results.json', 'RELEASE_MANIFEST.sha256'}
MANIFEST_NAME = 'LibraAI/RELEASE_MANIFEST.sha256'
CHUNK_SIZE = 64 * 1024

def _copy_and_hash(source, target):
    digest = hashlib.sha256()
    while True:
        chunk = source.read(CHUNK_SIZE)
        if not chunk:
            break
        target.write(chunk)
        digest.update(chunk)
    return digest.hexdigest()

def build_archive(root, destination):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    if destination == root or root in destination.parents:
        raise ValueError('Destination must be outside source tree')
    files = []
    for path in root.rglob('*'):
        rel = path.relative_to(root)
        if path.is_symlink():
            raise ValueError(f'Symlink forbidden: {rel}')
        if not path.is_file():
            continue
        if any(p in DEVELOPMENT_PARTS for p in rel.parts) or path.name in EXCLUDE_FILES:
            continue
        if path.name.lower() in BLOCKED_NAMES or path.suffix.lower() in BLOCKED_EXTENSIONS:
            raise ValueError(f'Sensitive file forbidden: {rel}')
        files.append((path, rel))
    # Keep release contents aligned with the buyer-facing preflight contract.
    # A ZIP must not be published if core deployment/payment files are missing.
    required = tuple(PREFLIGHT_REQUIRED) + ('buyer_preflight.py',)
    missing = [p for p in required if not any(str(rel) == p for _, rel in files)]
    if missing:
        raise ValueError(f'Missing required files: {missing}')
    # Build beside the destination and atomically replace it only after the
    # complete archive has been closed and CRC-verified. A failed build must
    # not destroy a previously valid release ZIP or leave a partial artifact.
    fd, temporary_name = tempfile.mkstemp(
        prefix=f'.{destination.name}.', suffix='.tmp', dir=destination.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with ZipFile(temporary, 'w', ZIP_DEFLATED) as archive:
            manifest_entries = []
            for path, rel in sorted(files, key=lambda item: str(item[1])):
                # Normalize ZIP metadata so source mtimes/host permissions do not
                # change the release artifact. Stream bytes to keep memory bounded.
                member_name = 'LibraAI/' + rel.as_posix()
                info = ZipInfo(member_name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                with path.open('rb') as source, archive.open(info, 'w', force_zip64=True) as target:
                    digest = _copy_and_hash(source, target)
                manifest_entries.append(f'{digest}  {member_name}\n')
            # A stable SHA-256 manifest lets recipients verify extracted files
            # independently. The manifest intentionally does not hash itself.
            manifest_info = ZipInfo(MANIFEST_NAME, date_time=(1980, 1, 1, 0, 0, 0))
            manifest_info.compress_type = ZIP_DEFLATED
            manifest_info.create_system = 3
            manifest_info.external_attr = (stat.S_IFREG | 0o644) << 16
            with archive.open(manifest_info, 'w') as manifest:
                manifest.write(''.join(manifest_entries).encode('utf-8'))
            bad = archive.testzip()
            if bad:
                raise ValueError(f'Corrupt archive member: {bad}')
        os.replace(temporary, destination)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return len(files) + 1

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python release_archive.py OUTPUT.zip')
    print(f'Packaged {build_archive(Path(__file__).parent, sys.argv[1])} files')
