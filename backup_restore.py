"""Offline SQLite backup and isolated restore verification.

Never overwrites an existing backup or a live database. Backup publication is atomic.
"""
import argparse
import datetime
import os
import pathlib
import sqlite3
import tempfile
from server import DB


def _check(path):
    # mode=ro prevents SQLite silently creating a missing database.
    uri = pathlib.Path(path).resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as conn:
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('SQLite integrity check failed')
        return conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]


def backup(destination, source=DB):
    src = pathlib.Path(source).resolve()
    target = pathlib.Path(destination).resolve()
    if not src.is_file():
        raise FileNotFoundError(f'Database not found: {src}')
    if src == target:
        raise ValueError('Destination must differ from source')
    if target.exists():
        raise FileExistsError(f'Refusing to overwrite existing backup: {target}')
    _check(src)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix='.libra-backup-', suffix='.db', dir=target.parent)
    os.close(fd)
    temporary = pathlib.Path(temp_name)
    try:
        with sqlite3.connect(str(src)) as original, sqlite3.connect(str(temporary)) as copy:
            original.backup(copy)
        _check(temporary)
        # Atomic publication; exclusive destination creation prevents overwriting.
        os.link(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def verify_restore(backup_path):
    src = pathlib.Path(backup_path).resolve()
    if not src.is_file():
        raise FileNotFoundError(f'Backup not found: {src}')
    _check(src)
    with tempfile.TemporaryDirectory() as tmp:
        restored = pathlib.Path(tmp) / 'restored.db'
        with sqlite3.connect(str(src)) as original, sqlite3.connect(str(restored)) as copy:
            original.backup(copy)
        return _check(restored)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=DB)
    parser.add_argument('--destination', default='backups/libra-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '.db')
    args = parser.parse_args()
    path = backup(args.destination, args.source)
    print(f'Backup: {path}; verified isolated restore with {verify_restore(path)} tables')
