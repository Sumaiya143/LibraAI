import sqlite3
import tempfile
import unittest
from pathlib import Path
from backup_manager import backup_database

class BackupNoClobberTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'live.db'
        with sqlite3.connect(self.source) as conn:
            conn.executescript('CREATE TABLE users(id INTEGER); CREATE TABLE books(id INTEGER);')

    def test_existing_backup_is_not_overwritten(self):
        dest = self.root / 'backup.db'
        dest.write_bytes(b'KEEP EXISTING BACKUP')
        with self.assertRaises(FileExistsError):
            backup_database(self.source, dest)
        self.assertEqual(dest.read_bytes(), b'KEEP EXISTING BACKUP')

    def test_symlink_destination_is_not_followed_or_replaced(self):
        target = self.root / 'sensitive.txt'
        target.write_text('keep')
        dest = self.root / 'backup.db'
        try:
            dest.symlink_to(target)
        except OSError:
            self.skipTest('Symlinks not supported on this platform')
        with self.assertRaises(FileExistsError):
            backup_database(self.source, dest)
        self.assertTrue(dest.is_symlink())
        self.assertEqual(target.read_text(), 'keep')

    def test_successful_backup_is_private_and_cannot_be_repeated(self):
        dest = self.root / 'backup.db'
        backup_database(self.source, dest)
        self.assertGreater(dest.stat().st_size, 0)
        with self.assertRaises(FileExistsError):
            backup_database(self.source, dest)

if __name__ == '__main__':
    unittest.main()
