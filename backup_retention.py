"""Conservative retention for verified local LibraAI SQLite backups.

Dry-run by default. Never removes backups if any candidate has an invalid digest.
An independent encrypted offsite backup is still required.
"""
import argparse
import datetime as dt
import hashlib
import re
from pathlib import Path

NAME = re.compile(r"libraai-(\d{8}T\d{6}Z)\.db\Z")
DIGEST = re.compile(r"[0-9a-fA-F]{64}\Z")


def _verified(file, checksum):
    if file.is_symlink() or checksum.is_symlink() or not file.is_file() or not checksum.is_file():
        return False
    try:
        parts = checksum.read_text(encoding="ascii").strip().split()
        if len(parts) != 2 or not DIGEST.fullmatch(parts[0]) or parts[1].lstrip('*') != file.name:
            return False
        with file.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        return actual == parts[0].lower()
    except (OSError, UnicodeError):
        return False


def plan_retention(directory, keep=14, now=None):
    if keep < 2:
        raise ValueError("At least two verified backups must be retained")
    root = Path(directory)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Backup directory must be an existing non-symlink directory")
    now = now or dt.datetime.now(dt.timezone.utc)
    candidates = []
    for file in root.iterdir():
        match = NAME.fullmatch(file.name)
        if not match or file.is_symlink() or not file.is_file():
            continue
        checksum = root / (file.name + '.sha256')
        try:
            stamp = dt.datetime.strptime(match.group(1), '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        if stamp > now + dt.timedelta(minutes=5):
            continue
        # Fail closed: a malformed or corrupted pair could be the newest backup.
        # Do not delete anything until an operator resolves it.
        if not _verified(file, checksum):
            raise ValueError(f"Unverified backup pair: {file.name}; retention aborted")
        candidates.append((stamp, file, checksum))
    candidates.sort(key=lambda item: (item[0], item[1].name), reverse=True)
    return [(file, checksum) for _, file, checksum in candidates[keep:]]


def main():
    parser = argparse.ArgumentParser(description='Review or prune older verified LibraAI backups')
    parser.add_argument('directory')
    parser.add_argument('--keep', type=int, default=14)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        planned = plan_retention(args.directory, args.keep)
    except ValueError as exc:
        parser.error(str(exc))
    for backup, checksum in planned:
        print(('DELETE' if args.apply else 'WOULD DELETE') + ': ' + backup.name)
        if args.apply:
            if not _verified(backup, checksum):
                raise RuntimeError('Backup changed since planning; aborting')
            backup.unlink()
            checksum.unlink()
    print(f"{'Removed' if args.apply else 'Eligible'}: {len(planned)} backup pair(s)")


if __name__ == '__main__':
    main()
