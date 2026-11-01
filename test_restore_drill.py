import sqlite3
import tempfile
import unittest
from pathlib import Path
from restore_drill import run_drill

class RestoreDrillTests(unittest.TestCase):
    def test_restore_drill_preserves_rows_and_source(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / 'live.db'
            with sqlite3.connect(db) as conn:
                conn.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)')
                conn.execute('CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT)')
                conn.execute('INSERT INTO users VALUES (1, ?)', ('Test user',))
                conn.execute('INSERT INTO books VALUES (1, ?)', ('Sample',))
            self.assertTrue(run_drill(db)['backup_restore_match'])
            with sqlite3.connect(db) as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)
    def test_missing_database_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                run_drill(Path(folder) / 'missing.db')
    def test_invalid_schema_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / 'wrong.db'
            with sqlite3.connect(db) as conn:
                conn.execute('CREATE TABLE other (id INTEGER)')
            with self.assertRaises(ValueError):
                run_drill(db)

if __name__ == '__main__':
    unittest.main()
