"""Offline non-destructive LibraAI SQLite backup/restore rehearsal.

Run: python backup_restore_drill.py --db /secure/libraai.db
Does not replace or alter the source database; report excludes customer records.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import tempfile
from backup_manager import backup_database, restore_database, verify_database


def fingerprint(path):
    """Compare logical data across backup/restore, including all table contents."""
    import hashlib
    digest = hashlib.sha256()
    uri = Path(path).resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as db:
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        for table in tables:
            # Include schema, not just data: indexes/triggers/constraints matter on restore.
            schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]
            digest.update((schema or '').encode('utf-8'))
            # Table names originate from SQLite schema, not user input.
            quoted = '"' + table.replace('"', '""') + '"'
            digest.update(table.encode('utf-8'))
            for row in db.execute('SELECT * FROM ' + quoted):
                for value in row:
                    if isinstance(value, bytes):
                        payload = value
                        kind = b'b'
                    elif value is None:
                        payload, kind = b'', b'n'
                    else:
                        payload, kind = str(value).encode('utf-8'), type(value).__name__.encode('ascii')
                    digest.update(len(kind).to_bytes(4, 'big') + kind)
                    digest.update(len(payload).to_bytes(8, 'big') + payload)
        # Include indexes, views and triggers, including their definitions.
        for kind, name, table_name, ddl in db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE type IN ('index','view','trigger') ORDER BY type,name"):
            for part in (kind, name, table_name, ddl or ''):
                payload = part.encode('utf-8')
                digest.update(len(payload).to_bytes(8, 'big') + payload)
        return digest.hexdigest(), len(tables)


def run_drill(source):
    source = Path(source)
    verify_database(source)
    with tempfile.TemporaryDirectory(prefix='libraai-restore-drill-') as temp:
        backup = Path(temp) / 'backup.db'
        restored = Path(temp) / 'restored.db'
        backup_database(source, backup)
        # Compare the immutable backup snapshot, not a moving live source.
        # SQLite online backup captures a consistent snapshot even with WAL writers.
        before, tables = fingerprint(backup)
        restore_database(backup, restored)
        verify_database(restored)
        after, restored_tables = fingerprint(restored)
        if before != after or tables != restored_tables:
            raise ValueError('Backup/restore data mismatch; source may have changed during drill')
    return {'backup_restore_verified': True, 'tables_checked': tables,
            'source_unchanged_by_drill': True, 'snapshot_consistent': True,
            'note': 'Backup snapshot vs restored copy; live source may receive concurrent writes. Not disaster recovery certification'}




def run_verified_backup_drill(backup, manifest, secret=None, require_hmac=True):
    """Authenticate a retained backup, then rehearse restoring it to a disposable DB.

    This deliberately never writes to the original backup or production database.
    Authentication is required by default; use require_hmac=False only for legacy
    unsigned backups in a trusted offline environment.
    """
    from backup_manifest import verify_manifest
    from backup_manager import restore_database

    backup = Path(backup)
    manifest = Path(manifest)
    # Validate the retained artifact before attempting a restore.
    evidence = verify_manifest(backup, manifest, secret=secret, require_hmac=require_hmac)
    with tempfile.TemporaryDirectory(prefix='libraai-verified-recovery-') as temp:
        restored = Path(temp) / 'restored.db'
        restore_database(backup, restored)
        verify_database(restored)
        # Re-check original artifact after the copy to detect accidental mutation
        # during the recovery rehearsal. This is not an adversarial filesystem lock.
        verify_manifest(backup, manifest, secret=secret, require_hmac=require_hmac)
        original_fingerprint, original_tables = fingerprint(backup)
        restored_fingerprint, restored_tables = fingerprint(restored)
        if original_fingerprint != restored_fingerprint or original_tables != restored_tables:
            raise ValueError('Restored database does not match authenticated backup')
    return {'verified_backup_restore': True,
            'manifest_authenticated': evidence['authenticated'],
            'tables_checked': original_tables,
            'original_backup_unchanged': True,
            'note': 'Offline restore rehearsal only; not a production disaster recovery certification'}


if __name__ == '__main__':
    import os
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--db', help='Live source database; creates a temporary snapshot')
    source.add_argument('--backup', help='Existing backup artifact to verify and restore')
    parser.add_argument('--manifest', help='Manifest required with --backup')
    parser.add_argument('--hmac-key-env', help='Environment variable containing HMAC secret')
    parser.add_argument('--allow-unsigned', action='store_true', help='Only for trusted offline legacy backups')
    args = parser.parse_args()
    if args.backup and not args.manifest:
        parser.error('--backup requires --manifest')
    if args.db and (args.manifest or args.hmac_key_env or args.allow_unsigned):
        parser.error('Manifest options are only valid with --backup')
    secret = None
    if args.hmac_key_env:
        value = os.environ.get(args.hmac_key_env)
        if value is None:
            parser.error('HMAC environment variable is not set')
        secret = value.encode('utf-8')
    try:
        result = (run_drill(args.db) if args.db else
                  run_verified_backup_drill(args.backup, args.manifest, secret,
                                            require_hmac=not args.allow_unsigned))
        print(json.dumps(result, indent=2))
    except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, 'Backup drill failed: ' + str(exc) + '\n')
