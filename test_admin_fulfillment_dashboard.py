import sqlite3
import unittest
from admin_fulfillment_dashboard import dashboard_data

class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.executescript('''
        CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,status TEXT,address TEXT);
        CREATE TABLE order_items(order_id INTEGER,book_id INTEGER,format TEXT,quantity INTEGER);
        CREATE TABLE payment_attempts(order_id INTEGER,state TEXT);
        CREATE TABLE print_shipments(order_id INTEGER,state TEXT);
        CREATE TABLE digital_entitlements(order_id INTEGER,user_id INTEGER,book_id INTEGER);
        CREATE TABLE licensed_documents(book_id INTEGER,access_policy TEXT);
        INSERT INTO orders VALUES(1,1,'Pending','secret address');
        INSERT INTO orders VALUES(2,2,'Pending','another secret');
        INSERT INTO order_items VALUES(1,11,'print',1);
        INSERT INTO order_items VALUES(2,12,'ebook',1);
        ''')
    def tearDown(self): self.conn.close()
    def test_no_pii(self):
        rows=dashboard_data(self.conn)
        self.assertEqual([r['order_id'] for r in rows],[2,1])
        self.assertNotIn('address',str(rows))
        self.assertNotIn('user_id',str(rows))
    def test_exceptions_only(self):
        self.conn.execute("UPDATE orders SET status='Processing' WHERE id=1")
        self.assertEqual([r['order_id'] for r in dashboard_data(self.conn,exceptions_only=True)],[1])
    def test_pagination(self):
        self.assertEqual(dashboard_data(self.conn,limit=1,offset=1)[0]['order_id'],1)
    def test_rejects_bad_pagination(self):
        for limit,offset in [(0,0),(101,0),(1,-1),(1,1000001),(True,0)]:
            with self.subTest(limit=limit,offset=offset):
                with self.assertRaises(ValueError): dashboard_data(self.conn,limit,offset)
    def test_boolean_filter_required(self):
        with self.assertRaises(ValueError): dashboard_data(self.conn,exceptions_only='1')

if __name__=='__main__': unittest.main()
