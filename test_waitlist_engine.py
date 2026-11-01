import unittest, sqlite3
from waitlist_engine import setup, join, cancel, offer_next, accept, WaitlistError
class WaitlistTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.executescript('CREATE TABLE users(id INTEGER PRIMARY KEY); CREATE TABLE books(id INTEGER PRIMARY KEY); INSERT INTO users VALUES(1),(2); INSERT INTO books VALUES(9);')
        setup(self.c)
    def tearDown(self): self.c.close()
    def test_fifo_and_accept(self):
        a=join(self.c,1,9); b=join(self.c,2,9)
        self.assertEqual(offer_next(self.c,9),a)
        with self.assertRaises(WaitlistError): offer_next(self.c,9)
        self.assertEqual(accept(self.c,1,a),9)
        self.assertEqual(offer_next(self.c,9),b)
    def test_duplicate(self):
        join(self.c,1,9)
        with self.assertRaises(WaitlistError): join(self.c,1,9)
    def test_ownership(self):
        a=join(self.c,1,9)
        with self.assertRaises(WaitlistError): cancel(self.c,2,a)
    def test_expiry(self):
        a=join(self.c,1,9);offer_next(self.c,9)
        self.c.execute("UPDATE book_waitlist SET expires_at='2000-01-01' WHERE id=?",(a,))
        with self.assertRaises(WaitlistError): accept(self.c,1,a)
    def test_cancel_and_rejoin(self):
        a=join(self.c,1,9);cancel(self.c,1,a)
        self.assertNotEqual(join(self.c,1,9),a)
if __name__=='__main__': unittest.main()
