import sqlite3
import tempfile
import unittest
from pathlib import Path
from backup_restore_drill import run_drill, fingerprint


class BackupRestoreDrillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'sample.db'
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE TABLE users (id INTEGER, name TEXT)')
            conn.execute('CREATE TABLE books (id INTEGER, title TEXT)')
            conn.execute('INSERT INTO users VALUES (1, ?)', ('Private User',))
            conn.execute('INSERT INTO books VALUES (1, ?)', ('Example',))

    def test_roundtrip(self):
        result = run_drill(self.db)
        self.assertTrue(result['backup_restore_verified'])
        self.assertEqual(result['tables_checked'], 2)
        self.assertNotIn('Private User', str(result))

    def test_source_remains_unchanged(self):
        before = self.db.read_bytes()
        run_drill(self.db)
        self.assertEqual(self.db.read_bytes(), before)

    def test_changed_data_changes_fingerprint(self):
        before, _ = fingerprint(self.db)
        with sqlite3.connect(self.db) as conn:
            conn.execute('UPDATE users SET name=?', ('Different',))
        after, _ = fingerprint(self.db)
        self.assertNotEqual(before, after)

    def test_schema_changes_affect_fingerprint(self):
        before, _ = fingerprint(self.db)
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE INDEX idx_books_title ON books(title)')
        after, _ = fingerprint(self.db)
        self.assertNotEqual(before, after)

    def test_wal_database_roundtrip(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('INSERT INTO books VALUES (2, ?)', ('WAL book',))
        result = run_drill(self.db)
        self.assertTrue(result['snapshot_consistent'])

    def test_restore_includes_schema_objects(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE INDEX idx_users_name ON users(name)')
            conn.execute('CREATE VIEW book_titles AS SELECT title FROM books')
        self.assertTrue(run_drill(self.db)['backup_restore_verified'])

    def test_missing_database_rejected(self):
        with self.assertRaises(FileNotFoundError):
            run_drill(Path(self.temp.name) / 'missing.db')
