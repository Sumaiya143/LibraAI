import sqlite3
import tempfile
import unittest
from pathlib import Path
from db_operations import backup, restore, _verify

class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.src=self.base/'live.sqlite3'
        with sqlite3.connect(self.src) as db:
            db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT)')
            db.execute('CREATE TABLE books(id INTEGER PRIMARY KEY, title TEXT)')
            db.execute("INSERT INTO users(name) VALUES('reader')")
    def test_backup_roundtrip(self):
        target=backup(self.src,self.base/'backup.sqlite3')
        self.assertTrue(_verify(target))
        with sqlite3.connect(target) as db:
            self.assertEqual(db.execute('SELECT name FROM users').fetchone()[0], 'reader')
    def test_no_overwrite(self):
        with self.assertRaises(ValueError): backup(self.src,self.src)
        backup(self.src,self.base/'backup.sqlite3')
        with self.assertRaises(FileExistsError): backup(self.src,self.base/'backup.sqlite3')
    def test_restore_requires_stopped_app(self):
        with self.assertRaises(RuntimeError): restore(self.src,self.base/'restored.sqlite3')
    def test_restore(self):
        target=restore(self.src,self.base/'restored.sqlite3',app_stopped=True)
        self.assertTrue(_verify(target))
    def test_invalid_database(self):
        bogus=self.base/'bogus.db'
        bogus.write_bytes(b'not sqlite')
        with self.assertRaises(sqlite3.DatabaseError): _verify(bogus)
    def test_wrong_schema(self):
        bogus=self.base/'other.db'
        with sqlite3.connect(bogus) as db: db.execute('CREATE TABLE unrelated(x)')
        with self.assertRaises(RuntimeError): _verify(bogus)

if __name__=='__main__':unittest.main()
