import sqlite3
import unittest
from commerce_engine import setup, place_sandbox_order, CheckoutError

class CheckoutAmountHardeningTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        self.conn.executescript('''CREATE TABLE books(id INTEGER PRIMARY KEY,title TEXT,price REAL,stock INTEGER);
          CREATE TABLE cart(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,qty INTEGER,format TEXT);
          CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,total REAL,status TEXT,address TEXT,created TEXT);''')
        setup(self.conn)
        self.conn.execute("INSERT INTO books VALUES(1,'Sample',12.50,10)")
        self.conn.execute("INSERT INTO cart VALUES(1,7,1,2,'Print')")
        self.conn.commit()
    def tearDown(self): self.conn.close()
    def assert_rejected_without_mutation(self, **kwargs):
        with self.assertRaises(CheckoutError):
            place_sandbox_order(self.conn, kwargs.pop('user_id',7), 'checkout-test-123', **kwargs)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT stock FROM books').fetchone()[0],10)
    def test_nonfinite_catalog_price(self):
        for value in ('NaN','Infinity','-Infinity'):
            self.conn.execute('UPDATE books SET price=?',(value,))
            self.conn.commit()
            self.assert_rejected_without_mutation()
    def test_fractional_cent_price(self):
        self.conn.execute('UPDATE books SET price=?',(1.001,))
        self.conn.commit()
        self.assert_rejected_without_mutation()
    def test_excessive_price(self):
        self.conn.execute('UPDATE books SET price=?',(1e20,))
        self.conn.commit()
        self.assert_rejected_without_mutation()
    def test_invalid_inputs(self):
        for opts in ({'user_id':True},{'user_id':0},{'coupon':None},{'address':None},{'coupon':'A'*65}):
            self.assert_rejected_without_mutation(**opts)
    def test_valid_mixed_cart_preserves_print_stock(self):
        self.conn.execute("INSERT INTO cart VALUES(2,7,1,1,'eBook')")
        self.conn.commit()
        order_id,created=place_sandbox_order(self.conn,7,'checkout-test-123')
        self.assertTrue(created)
        self.assertEqual(self.conn.execute('SELECT stock FROM books').fetchone()[0],8)
        self.assertEqual(self.conn.execute('SELECT SUM(line_total_cents) FROM order_items WHERE order_id=?',(order_id,)).fetchone()[0],3750)
        self.assertEqual(self.conn.execute('SELECT total_cents FROM order_amounts WHERE order_id=?',(order_id,)).fetchone()[0],3750)

if __name__=='__main__': unittest.main()
