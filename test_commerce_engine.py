import sqlite3, unittest
from commerce_engine import setup, place_sandbox_order, CheckoutError

class CommerceTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.executescript('''CREATE TABLE books(id INTEGER PRIMARY KEY,title TEXT,price REAL,stock INTEGER);CREATE TABLE cart(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,qty INTEGER,format TEXT);CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,total REAL,status TEXT,address TEXT,created TEXT);''')
        setup(self.c)
        self.c.execute("INSERT INTO books VALUES(1,'Test',10.25,3)")
        self.c.execute("INSERT INTO cart VALUES(1,7,1,2,'Print')")
        self.c.commit()
    def tearDown(self): self.c.close()
    def test_success_and_idempotency(self):
        a=place_sandbox_order(self.c,7,'unique-request-123','LIBRA10')
        b=place_sandbox_order(self.c,7,'unique-request-123','LIBRA10')
        self.assertEqual(a[0],b[0]);self.assertTrue(a[1]);self.assertFalse(b[1])
        self.assertEqual(self.c.execute('SELECT stock FROM books').fetchone()[0],1)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM order_items').fetchone()[0],1)
        self.assertEqual(self.c.execute('SELECT total FROM orders').fetchone()[0],18.45)
    def test_out_of_stock_rolls_back(self):
        self.c.execute('UPDATE cart SET qty=4');self.c.commit()
        with self.assertRaises(CheckoutError): place_sandbox_order(self.c,7,'another-request-123')
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM orders').fetchone()[0],0)
        self.assertEqual(self.c.execute('SELECT stock FROM books').fetchone()[0],3)
    def test_empty_cart_rejected(self):
        self.c.execute('DELETE FROM cart');self.c.commit()
        with self.assertRaises(CheckoutError):place_sandbox_order(self.c,7,'third-request-123')
if __name__=='__main__': unittest.main()
