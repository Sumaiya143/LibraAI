"""Non-destructive SQLite backup/restore drill; never touches the live DB.

Usage: python restore_drill.py /absolute/path/to/libraai.db
Returns nonzero on failure. The report contains no user records or secrets.
"""
import argparse
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from backup_manager import backup_database, restore_database, verify_database


def fingerprint(conn):
    """Compare database content logically, independent of SQLite page layout."""
    digest = hashlib.sha256()
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    for table in tables:
        # Quote names returned from sqlite_master to avoid malformed SQL.
        safe = '"' + table.replace('"', '""') + '"'
        digest.update(json.dumps(['table', table]).encode())
        columns = [r[1] for r in conn.execute(f'PRAGMA table_info({safe})')]
        digest.update(json.dumps(columns).encode())
        # Sorting encoded rows avoids relying on table scan order.
        rows = []
        for row in conn.execute(f'SELECT * FROM {safe}'):
            serialized = [v.hex() if isinstance(v, bytes) else v for v in row]
            rows.append(json.dumps(serialized, ensure_ascii=True, default=str, separators=(',', ':')))
        for value in sorted(rows):
            digest.update(value.encode())
            digest.update(b'\n')
    return digest.hexdigest(), len(tables)


def run_drill(source):
    source = Path(source).resolve()
    verify_database(source)
    with tempfile.TemporaryDirectory(prefix='libraai-restore-drill-') as directory:
        backup = Path(directory) / 'backup.db'
        restored = Path(directory) / 'restored.db'
        backup_database(source, backup)
        restore_database(backup, restored)
        verify_database(restored)
        # Compare backup to restore. A live source can change while backup runs.
        with sqlite3.connect(f'file:{backup}?mode=ro', uri=True) as a, sqlite3.connect(f'file:{restored}?mode=ro', uri=True) as b:
            original, count = fingerprint(a)
            recovered, _ = fingerprint(b)
        if original != recovered:
            raise ValueError('Restored data differs from backup')
        return {'passed': True, 'tables_verified': count, 'backup_restore_match': True,
                'note': 'Local drill only; does not certify offsite backups or recovery objectives'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database')
    args = parser.parse_args()
    try:
        print(json.dumps(run_drill(args.database), indent=2))
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({'passed': False, 'error': type(exc).__name__}))
        raise SystemExit(1)
