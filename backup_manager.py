"""Consistent SQLite backups and integrity verification for LibraAI.

Usage: python backup_manager.py backup path/to/libraai.db path/to/backup.db
       python backup_manager.py verify path/to/backup.db
       python backup_manager.py restore path/to/backup.db path/to/restored.db

Stop application writers before restoring a live database. Backups may contain
personal data; protect them with encryption and restricted access.
"""
import argparse
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile


def verify_database(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    # Open read-only so verification never creates or changes a database.
    uri = path.resolve().as_uri() + '?mode=ro'
    conn = sqlite3.connect(uri, uri=True)
    try:
        result = conn.execute('PRAGMA integrity_check').fetchone()[0]
        if result != 'ok':
            raise ValueError(f'SQLite integrity check failed: {result}')
        # integrity_check alone does not detect broken foreign-key references.
        fk_errors = conn.execute('PRAGMA foreign_key_check').fetchmany(5)
        if fk_errors:
            raise ValueError('SQLite foreign-key integrity check failed')
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'users', 'books'}.issubset(tables):
            raise ValueError('Not a LibraAI database: missing core tables')
    finally:
        conn.close()
    return True


def backup_database(source, destination):
    source, destination = Path(source), Path(destination)
    verify_database(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() == destination.resolve():
        raise ValueError('Source and destination must differ')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('Backup refuses to overwrite an existing destination')
    fd, temp = tempfile.mkstemp(prefix='.libraai-backup-', suffix='.db', dir=destination.parent)
    os.close(fd)
    try:
        src = sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)
        try:
            dst = sqlite3.connect(temp)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        verify_database(temp)
        os.chmod(temp, 0o600)
        # Atomic no-clobber publish: never replace an existing backup or symlink.
        if destination.exists() or destination.is_symlink():
            raise FileExistsError('Backup refuses to overwrite an existing destination')
        try:
            os.link(temp, destination)
        except (AttributeError, OSError, PermissionError):
            if destination.exists() or destination.is_symlink():
                raise FileExistsError('Backup refuses to overwrite an existing destination')
            # Atomic publish without clobber on platforms where link lacks privilege
            if hasattr(os, 'O_EXCL') and hasattr(os, 'O_CREAT'):
                # Read temp bytes and write exclusively
                with open(temp, 'rb') as sf:
                    data = sf.read()
                fd_out = os.open(str(destination), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o600)
                with open(fd_out, 'wb', closefd=True) as df:
                    df.write(data)
            else:
                shutil.copy2(temp, destination)
    finally:
        if os.path.exists(temp):
            try:
                os.unlink(temp)
            except OSError:
                pass
    return destination


def restore_database(backup, destination):
    backup, destination = Path(backup), Path(destination)
    verify_database(backup)
    if destination.exists():
        raise FileExistsError('Restore refuses to overwrite an existing database')
    return backup_database(backup, destination)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['backup', 'verify', 'restore'])
    p.add_argument('source')
    p.add_argument('destination', nargs='?')
    a = p.parse_args()
    if a.command == 'verify':
        verify_database(a.source)
        print('Database integrity: OK')
    else:
        if not a.destination:
            p.error('destination required')
        fn = backup_database if a.command == 'backup' else restore_database
        print(fn(a.source, a.destination))
