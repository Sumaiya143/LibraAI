"""Regression tests: reject structurally valid but referentially corrupt backups."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from backup_manager import backup_database, restore_database, verify_database


class ForeignKeyBackupTests(unittest.TestCase):
    def make_db(self, path, broken=False):
        with sqlite3.connect(path) as conn:
            conn.executescript('''
                PRAGMA foreign_keys=OFF;
                CREATE TABLE users(id INTEGER PRIMARY KEY);
                CREATE TABLE books(id INTEGER PRIMARY KEY);
                CREATE TABLE orders(id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id));
                INSERT INTO users VALUES(1);
                INSERT INTO books VALUES(1);
            ''')
            conn.execute('INSERT INTO orders VALUES(1, ?)', (999 if broken else 1,))

    def test_rejects_dangling_foreign_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'broken.db'
            self.make_db(db, broken=True)
            with self.assertRaisesRegex(ValueError, 'foreign-key'):
                verify_database(db)

    def test_refuses_backup_of_corrupt_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, dest = Path(tmp) / 'broken.db', Path(tmp) / 'backup.db'
            self.make_db(db, broken=True)
            with self.assertRaisesRegex(ValueError, 'foreign-key'):
                backup_database(db, dest)
            self.assertFalse(dest.exists())

    def test_refuses_restore_of_corrupt_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, dest = Path(tmp) / 'broken.db', Path(tmp) / 'restored.db'
            self.make_db(db, broken=True)
            with self.assertRaisesRegex(ValueError, 'foreign-key'):
                restore_database(db, dest)
            self.assertFalse(dest.exists())

    def test_valid_foreign_keys_backup_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, backup, dest = (Path(tmp) / name for name in ('source.db', 'backup.db', 'restore.db'))
            self.make_db(db)
            backup_database(db, backup)
            restore_database(backup, dest)
            self.assertTrue(verify_database(dest))


if __name__ == '__main__':
    unittest.main()
