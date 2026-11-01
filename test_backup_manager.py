import sqlite3
import tempfile
import unittest
from pathlib import Path
from backup_manager import backup_database, restore_database, verify_database

class BackupTests(unittest.TestCase):
    def test_backup_and_restore_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            original=root/'live.db'
            with sqlite3.connect(original) as c:
                c.executescript('CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT); CREATE TABLE books(id INTEGER PRIMARY KEY, title TEXT); INSERT INTO users(name) VALUES (\'A\');')
            backup=root/'backup.db'
            backup_database(original, backup)
            self.assertTrue(verify_database(backup))
            restored=root/'restored.db'
            restore_database(backup, restored)
            with sqlite3.connect(restored) as c:
                self.assertEqual(c.execute('SELECT name FROM users').fetchone()[0], 'A')
            with self.assertRaises(FileExistsError):
                restore_database(backup, restored)
    def test_rejects_invalid_database(self):
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/'broken.db'
            f.write_text('not sqlite')
            with self.assertRaises(sqlite3.DatabaseError):
                verify_database(f)
if __name__=='__main__': unittest.main()
