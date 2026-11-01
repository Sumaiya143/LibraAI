"""Offline restore drill for a market backup; never touches the live database.

Usage: python market_restore_drill.py private-backups/libraai-...db
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

from backup_manager import restore_database, verify_database


def restore_drill(backup_path):
    backup = Path(backup_path).resolve(strict=True)
    checksum = Path(str(backup) + '.sha256')
    if not checksum.is_file():
        raise ValueError('Missing checksum sidecar; cannot verify backup provenance')
    parts = checksum.read_text(encoding='utf-8').strip().split()
    if len(parts) != 2 or len(parts[0]) != 64 or parts[1].lstrip('*') != backup.name:
        raise ValueError('Invalid checksum sidecar')
    expected = parts[0].lower()
    if any(ch not in '0123456789abcdef' for ch in expected):
        raise ValueError('Invalid checksum digest')
    with backup.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != expected:
        raise ValueError('Backup checksum mismatch')
    verify_database(backup)
    with tempfile.TemporaryDirectory(prefix='libraai-restore-drill-') as folder:
        restored = Path(folder) / 'restored.db'
        restore_database(backup, restored)
        verify_database(restored)
        with sqlite3.connect(f'file:{restored}?mode=ro', uri=True) as db:
            counts = {table: db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                      for table in ('users', 'books')}
    return {'result': 'PASS', 'checksum_verified': True,
            'isolated_restore_verified': True, 'row_counts': counts}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backup')
    args = parser.parse_args()
    print(json.dumps(restore_drill(args.backup), indent=2))
