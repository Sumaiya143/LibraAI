"""Mixed format checkout inventory regression coverage."""
import sqlite3
import unittest
from commerce_engine import setup, place_sandbox_order, CheckoutError

class MixedCartStockTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.executescript('''
            CREATE TABLE books(id INTEGER PRIMARY KEY,title TEXT,price REAL,stock INTEGER);
            CREATE TABLE cart(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,qty INTEGER,format TEXT);
            CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,total REAL,status TEXT,address TEXT,created TEXT);
            INSERT INTO books VALUES(1,'Hybrid book',12.00,2);
            INSERT INTO books VALUES(2,'Digital only',5.00,0);
        ''')
        setup(self.conn)
    def tearDown(self):
        self.conn.close()
    def add(self, book, qty, fmt):
        self.conn.execute('INSERT INTO cart(user_id,book_id,qty,format) VALUES(7,?,?,?)', (book,qty,fmt))
        self.conn.commit()
    def test_ebook_zero_stock_still_checkout(self):
        self.add(2, 1, 'eBook')
        place_sandbox_order(self.conn,7,'ebook-zero-stock')
        self.assertEqual(self.conn.execute('SELECT stock FROM books WHERE id=2').fetchone()[0],0)
    def test_mixed_cart_only_reserves_print_stock(self):
        self.add(1, 2, 'Print'); self.add(1, 3, 'eBook'); self.add(2, 1, 'eBook')
        order_id, _ = place_sandbox_order(self.conn,7,'mixed-cart-request')
        self.assertEqual(self.conn.execute('SELECT stock FROM books WHERE id=1').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT total_cents FROM order_amounts WHERE order_id=?',(order_id,)).fetchone()[0],6500)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM order_items WHERE order_id=?',(order_id,)).fetchone()[0],3)
    def test_duplicate_print_rows_cannot_oversell(self):
        self.add(1,2,'Print'); self.add(1,1,'Print')
        with self.assertRaises(CheckoutError):
            place_sandbox_order(self.conn,7,'duplicate-print-oversell')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT stock FROM books WHERE id=1').fetchone()[0],2)
    def test_ebook_does_not_consume_print_inventory(self):
        self.add(1,100,'eBook')
        place_sandbox_order(self.conn,7,'ebook-many-copies')
        self.assertEqual(self.conn.execute('SELECT stock FROM books WHERE id=1').fetchone()[0],2)
    def test_invalid_format_rejected_without_order(self):
        self.add(1,1,'Audio')
        with self.assertRaises(CheckoutError):
            place_sandbox_order(self.conn,7,'invalid-format-request')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0],0)

if __name__ == '__main__': unittest.main()
