import sqlite3
import unittest
from commerce_engine import setup, place_sandbox_order


class DiscountAllocationTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        self.conn.executescript('''CREATE TABLE books(id INTEGER PRIMARY KEY,title TEXT,price REAL,stock INTEGER);
        CREATE TABLE cart(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,qty INTEGER,format TEXT);
        CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,total REAL,status TEXT,address TEXT,created TEXT);''')
        setup(self.conn)
        self.conn.executemany('INSERT INTO books VALUES(?,?,?,?)',[(1,'A',1.01,10),(2,'B',2.02,10)])
        self.conn.executemany('INSERT INTO cart VALUES(?,?,?,?,?)',[(1,7,1,1,'eBook'),(2,7,2,1,'Print')])
        self.conn.commit()

    def tearDown(self): self.conn.close()

    def test_discount_exact_allocation(self):
        order,_=place_sandbox_order(self.conn,7,'discount-unique-123','LIBRA10')
        paid=self.conn.execute('SELECT total_cents FROM order_amounts WHERE order_id=?',(order,)).fetchone()[0]
        lines=[r[0] for r in self.conn.execute('SELECT line_total_cents FROM order_items WHERE order_id=? ORDER BY id',(order,))]
        self.assertEqual(paid,273)
        self.assertEqual(lines,[91,182])
        self.assertEqual(sum(lines),paid)

    def test_full_price_exact_allocation(self):
        order,_=place_sandbox_order(self.conn,7,'fullprice-unique-123')
        lines=[r[0] for r in self.conn.execute('SELECT line_total_cents FROM order_items WHERE order_id=? ORDER BY id',(order,))]
        self.assertEqual(lines,[101,202])

    def test_schema_migration_idempotent(self):
        setup(self.conn)
        setup(self.conn)
        self.assertEqual([r[1] for r in self.conn.execute('PRAGMA table_info(order_items)')].count('line_total_cents'),1)

    def test_one_cent_rounding_remainder(self):
        self.conn.execute('DELETE FROM cart')
        self.conn.execute('UPDATE books SET price=0.01')
        self.conn.executemany('INSERT INTO cart VALUES(?,?,?,?,?)',[(3,7,1,1,'eBook'),(4,7,2,1,'eBook')])
        self.conn.commit()
        order,_=place_sandbox_order(self.conn,7,'rounding-unique-123','LIBRA10')
        amounts=[r[0] for r in self.conn.execute('SELECT line_total_cents FROM order_items WHERE order_id=? ORDER BY id',(order,))]
        self.assertEqual(amounts,[1,1])

if __name__=='__main__': unittest.main()
