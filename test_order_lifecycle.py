import sqlite3
import unittest
from order_lifecycle import setup, cancel_unpaid_order, OrderLifecycleError

class OrderLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        self.conn.executescript('''
        CREATE TABLE books(id INTEGER PRIMARY KEY,stock INTEGER);
        CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,status TEXT);
        CREATE TABLE order_items(id INTEGER PRIMARY KEY,order_id INTEGER,book_id INTEGER,quantity INTEGER);
        INSERT INTO books VALUES(1,3);
        INSERT INTO orders VALUES(7,5,'Awaiting payment — sandbox only');
        INSERT INTO order_items VALUES(1,7,1,2);
        ''')
        setup(self.conn)
    def tearDown(self): self.conn.close()
    def stock(self): return self.conn.execute('SELECT stock FROM books WHERE id=1').fetchone()[0]
    def test_cancel_restores_stock_once(self):
        self.assertTrue(cancel_unpaid_order(self.conn,7,5))
        self.assertEqual(self.stock(),5)
        self.assertFalse(cancel_unpaid_order(self.conn,7,5))
        self.assertEqual(self.stock(),5)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM order_events').fetchone()[0],1)
    def test_other_user_cannot_cancel(self):
        with self.assertRaises(OrderLifecycleError): cancel_unpaid_order(self.conn,7,6)
        self.assertEqual(self.stock(),3)
    def test_paid_orders_cannot_cancel(self):
        self.conn.execute("UPDATE orders SET status='Paid' WHERE id=7"); self.conn.commit()
        with self.assertRaises(OrderLifecycleError): cancel_unpaid_order(self.conn,7,5)
        self.assertEqual(self.stock(),3)
    def test_missing_book_rolls_back(self):
        self.conn.execute('DELETE FROM books WHERE id=1'); self.conn.commit()
        with self.assertRaises(OrderLifecycleError): cancel_unpaid_order(self.conn,7,5)
        self.assertEqual(self.conn.execute('SELECT status FROM orders WHERE id=7').fetchone()[0], 'Awaiting payment — sandbox only')

if __name__=='__main__': unittest.main()
