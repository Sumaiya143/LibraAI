import sqlite3
import unittest
from credential_integrity import inspect_users, require_secure_credentials, CredentialIntegrityError

class CredentialIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        self.conn.execute('CREATE TABLE users (password TEXT)')
    def tearDown(self): self.conn.close()
    def test_empty_database(self):
        self.assertEqual(require_secure_credentials(self.conn)['users_checked'],0)
    def test_supported_hashes(self):
        self.conn.executemany('INSERT INTO users VALUES (?)',[('scrypt:32768:8:1$salt$hash',),('pbkdf2:sha256:1000000$salt$hash',)])
        self.assertEqual(require_secure_credentials(self.conn)['invalid_password_hashes'],0)
    def test_plaintext_rejected(self):
        self.conn.execute('INSERT INTO users VALUES (?)',('demo123',))
        with self.assertRaises(CredentialIntegrityError): require_secure_credentials(self.conn)
    def test_null_rejected(self):
        self.conn.execute('INSERT INTO users VALUES (NULL)')
        with self.assertRaises(CredentialIntegrityError): require_secure_credentials(self.conn)
    def test_unsupported_hash_rejected(self):
        self.conn.execute('INSERT INTO users VALUES (?)',('md5:abc',))
        with self.assertRaises(CredentialIntegrityError): require_secure_credentials(self.conn)
    def test_aggregate_only(self):
        self.conn.execute('INSERT INTO users VALUES (?)',('plaintext-secret',))
        self.assertEqual(inspect_users(self.conn),{'users_checked':1,'invalid_password_hashes':1})

if __name__=='__main__': unittest.main()
