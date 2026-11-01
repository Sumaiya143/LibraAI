import unittest, tempfile, sqlite3
from pathlib import Path
from unittest.mock import patch
from bootstrap_admin import bootstrap

class AdminBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=str(Path(self.temp.name)/'test.db')
        with sqlite3.connect(self.db) as c:
            c.execute('CREATE TABLE users(id INTEGER PRIMARY KEY,name TEXT,email TEXT UNIQUE,password TEXT,role TEXT,plan TEXT)')
    def tearDown(self): self.temp.cleanup()
    def test_creates_hashed_admin(self):
        bootstrap(self.db,'Admin','Admin@Example.com','a secure password 123')
        with sqlite3.connect(self.db) as c:
            row=c.execute('SELECT email,role,password FROM users').fetchone()
        self.assertEqual(row[0],'admin@example.com')
        self.assertEqual(row[1],'admin')
        self.assertNotEqual(row[2],'a secure password 123')
    def test_refuses_second_admin(self):
        bootstrap(self.db,'Admin','a@example.com','a secure password 123')
        with self.assertRaisesRegex(ValueError,'already exists'):
            bootstrap(self.db,'Other','b@example.com','a secure password 123')
    def test_rejects_weak_password(self):
        with self.assertRaisesRegex(ValueError,'12'):
            bootstrap(self.db,'Admin','a@example.com','short')
    def test_rejects_relative_db_path(self):
        with self.assertRaisesRegex(ValueError,'absolute'):
            bootstrap('relative.db','Admin','a@example.com','a secure password 123')

if __name__=='__main__': unittest.main()
