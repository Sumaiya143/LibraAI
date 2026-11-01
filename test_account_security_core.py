import hashlib
import sqlite3
import unittest
from account_security_core import change_password, PasswordChangeError

def hash_pw(p): return hashlib.sha256(p.encode()).hexdigest()
def verify(h,p): return h == hash_pw(p)

class AccountSecurityTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, password TEXT)')
        self.db.execute('INSERT INTO users VALUES (1,?)',(hash_pw('old-password-123'),))
    def tearDown(self): self.db.close()
    def change(self, old='old-password-123', new='new-password-456', uid=1):
        return change_password(self.db,uid,old,new,verify,hash_pw)
    def test_success(self):
        self.assertTrue(self.change())
        self.assertTrue(verify(self.db.execute('SELECT password FROM users').fetchone()[0],'new-password-456'))
    def test_wrong_old_password(self):
        with self.assertRaises(PasswordChangeError): self.change(old='wrong')
    def test_short_new_password(self):
        with self.assertRaises(PasswordChangeError): self.change(new='short')
    def test_same_password(self):
        with self.assertRaises(PasswordChangeError): self.change(new='old-password-123')
    def test_unknown_user(self):
        with self.assertRaises(PasswordChangeError): self.change(uid=999)
    def test_second_change_rejects_old_credential(self):
        self.change()
        with self.assertRaises(PasswordChangeError): self.change()

if __name__ == '__main__': unittest.main()
