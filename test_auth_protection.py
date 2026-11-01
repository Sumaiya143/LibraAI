import sqlite3
import unittest
from auth_protection import identity_key,blocked,failed,clear,MAX_ATTEMPTS,WINDOW_SECONDS
class TestAuthProtection(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.k=identity_key('USER@example.com','127.0.0.1','secret')
    def tearDown(self): self.c.close()
    def test_identity_normalization(self):
        self.assertEqual(self.k,identity_key(' user@example.com ','127.0.0.1','secret'))
        self.assertNotEqual(self.k,identity_key('user@example.com','127.0.0.2','secret'))
    def test_lockout_after_failures(self):
        for _ in range(MAX_ATTEMPTS): failed(self.c,self.k,1000)
        self.assertTrue(blocked(self.c,self.k,1001))
        self.assertFalse(blocked(self.c,self.k,1000+WINDOW_SECONDS))
    def test_success_resets(self):
        for _ in range(MAX_ATTEMPTS): failed(self.c,self.k,1000)
        clear(self.c,self.k)
        self.assertFalse(blocked(self.c,self.k,1001))
    def test_window_resets_counter(self):
        for _ in range(MAX_ATTEMPTS): failed(self.c,self.k,1000)
        failed(self.c,self.k,1000+WINDOW_SECONDS)
        self.assertFalse(blocked(self.c,self.k,1000+WINDOW_SECONDS))
    def test_expired_identities_are_pruned_on_failure(self):
        stale = identity_key('stale@example.com','127.0.0.3','secret')
        active = identity_key('active@example.com','127.0.0.4','secret')
        failed(self.c,stale,1000)
        failed(self.c,active,1000+WINDOW_SECONDS-1)
        failed(self.c,self.k,1000+WINDOW_SECONDS+1)
        rows = {row[0] for row in self.c.execute('SELECT identity FROM auth_failures')}
        self.assertNotIn(stale, rows)
        self.assertIn(active, rows)
        self.assertIn(self.k, rows)
    def test_future_timestamp_does_not_lock_out_identity(self):
        failed(self.c,self.k,2000)
        self.c.execute('UPDATE auth_failures SET attempts=? WHERE identity=?',(MAX_ATTEMPTS,self.k))
        self.c.execute('UPDATE auth_failures SET first_attempt=? WHERE identity=?',(3000,self.k))
        self.assertFalse(blocked(self.c,self.k,2001))
if __name__=='__main__':unittest.main()
