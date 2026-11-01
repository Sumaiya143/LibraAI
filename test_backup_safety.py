import pathlib
import sqlite3
import tempfile
import unittest
from backup_restore import backup, verify_restore

class BackupSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.db = self.root / 'source.db'
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE TABLE demo (id INTEGER PRIMARY KEY, title TEXT)')
            conn.execute('INSERT INTO demo(title) VALUES (?)', ('Book',))

    def test_backup_and_isolated_restore(self):
        dest = self.root / 'backups' / 'copy.db'
        self.assertEqual(backup(dest, self.db), dest)
        self.assertEqual(verify_restore(dest), 1)
        with sqlite3.connect(dest) as conn:
            self.assertEqual(conn.execute('SELECT title FROM demo').fetchone()[0], 'Book')

    def test_existing_backup_not_overwritten(self):
        dest = self.root / 'backup.db'
        dest.write_bytes(b'keep this backup')
        with self.assertRaises(FileExistsError):
            backup(dest, self.db)
        self.assertEqual(dest.read_bytes(), b'keep this backup')

    def test_source_never_overwritten(self):
        with self.assertRaises(ValueError):
            backup(self.db, self.db)

    def test_corrupt_source_rejected(self):
        self.db.write_bytes(b'not sqlite')
        with self.assertRaises(sqlite3.DatabaseError):
            backup(self.root / 'backup.db', self.db)
        self.assertFalse((self.root / 'backup.db').exists())

    def test_missing_backup_does_not_create_database(self):
        missing = self.root / 'missing.db'
        with self.assertRaises(FileNotFoundError):
            verify_restore(missing)
        self.assertFalse(missing.exists())

if __name__ == '__main__':
    unittest.main()
