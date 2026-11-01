import sqlite3
from pathlib import Path

def inspect_database(path):
    """Return a safe summary; never include database paths or row contents."""
    if not path or not Path(path).is_file():
        return {'ok': False, 'reason': 'database_missing'}
    try:
        connection = sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro', uri=True, timeout=2)
        try:
            check = connection.execute('PRAGMA quick_check').fetchone()
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            required = {'users', 'books', 'orders', 'loans', 'progress'}
            return {'ok': check is not None and check[0] == 'ok' and required <= names,
                    'schema_ok': required <= names,
                    'integrity_ok': bool(check and check[0] == 'ok')}
        finally:
            connection.close()
    except (sqlite3.Error, OSError, ValueError):
        return {'ok': False, 'reason': 'database_unavailable'}

