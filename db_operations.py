"""Offline SQLite backup, verification, and safe restore for LibraAI.

Backups are SQLite-consistent snapshots (including data from WAL). Never put
backups under a web-served directory. Restore only while the app is stopped.
"""
import argparse
import os
import sqlite3
import tempfile
from pathlib import Path


def _verify(path):
    uri = f"file:{Path(path).resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError("SQLite integrity check failed: " + result)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"users", "books"}.issubset(tables):
            raise RuntimeError("This is not a LibraAI database")
    finally:
        conn.close()
    return True


def backup(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if source == destination:
        raise ValueError("Source and destination must differ")
    if destination.exists():
        raise FileExistsError(destination)
    _verify(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.libraai-backup-', suffix='.sqlite3', dir=destination.parent)
    os.close(fd)
    try:
        original = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        try:
            copy = sqlite3.connect(temp)
            try:
                original.backup(copy)
            finally:
                copy.close()
        finally:
            original.close()
        _verify(temp)
        os.chmod(temp, 0o600)
        os.replace(temp, destination)
    finally:
        if os.path.exists(temp):
            try:
                os.unlink(temp)
            except OSError:
                pass
    return destination


def restore(source, destination, *, app_stopped=False):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not app_stopped:
        raise RuntimeError("Stop all application workers before restore; pass --app-stopped")
    if source == destination:
        raise ValueError("Source and destination must differ")
    if destination.exists():
        raise FileExistsError("Refusing to overwrite a database; move it aside first")
    _verify(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.libraai-restore-', suffix='.sqlite3', dir=destination.parent)
    os.close(fd)
    try:
        original = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        try:
            copy = sqlite3.connect(temp)
            try:
                original.backup(copy)
            finally:
                copy.close()
        finally:
            original.close()
        _verify(temp)
        os.chmod(temp, 0o600)
        os.replace(temp, destination)
    finally:
        if os.path.exists(temp):
            try:
                os.unlink(temp)
            except OSError:
                pass
    return destination

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description='LibraAI consistent backup and offline restore')
    parser.add_argument('action', choices=['backup','verify','restore'])
    parser.add_argument('source')
    parser.add_argument('destination', nargs='?')
    parser.add_argument('--app-stopped', action='store_true')
    args=parser.parse_args()
    if args.action=='verify': _verify(args.source); print('Verified OK')
    elif not args.destination: parser.error('Destination is required')
    elif args.action=='backup': print(backup(args.source,args.destination))
    else: print(restore(args.source,args.destination,app_stopped=args.app_stopped))
