import sqlite3
import unittest
from operations_dashboard import snapshot

class OperationsDashboardTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.executescript('''
          CREATE TABLE orders(id INTEGER PRIMARY KEY,total REAL,status TEXT);
          CREATE TABLE payment_attempts(id INTEGER PRIMARY KEY,order_id INTEGER,state TEXT,amount_cents INTEGER,currency TEXT);
          CREATE TABLE refund_requests(id INTEGER PRIMARY KEY,state TEXT);
          CREATE TABLE digital_entitlements(id INTEGER PRIMARY KEY,order_id INTEGER);
        ''')
    def tearDown(self): self.conn.close()
    def test_empty_clean(self):
        r=snapshot(self.conn)
        self.assertTrue(r['ready']); self.assertEqual(r['counts']['total_orders'],0)
    def test_pending_and_paid_counts(self):
        self.conn.execute("INSERT INTO orders VALUES(1,100,'Awaiting payment')")
        self.conn.execute("INSERT INTO orders VALUES(2,50,'Completed')")
        self.conn.execute("INSERT INTO payment_attempts VALUES(1,1,'pending',10000,'BDT')")
        self.conn.execute("INSERT INTO payment_attempts VALUES(2,2,'paid',5000,'BDT')")
        self.conn.execute("INSERT INTO digital_entitlements VALUES(1,2)")
        r=snapshot(self.conn)
        self.assertTrue(r['ready']); self.assertEqual(r['counts']['pending_payment_attempts'],1)
        self.assertEqual(r['counts']['active_digital_entitlements'],1)
    def test_refund_review_count(self):
        self.conn.execute("INSERT INTO refund_requests VALUES(1,'requested')")
        self.conn.execute("INSERT INTO refund_requests VALUES(2,'approved')")
        self.assertEqual(snapshot(self.conn)['counts']['refund_requests_needing_review'],1)
    def test_unverified_paid_order_fails_closed(self):
        self.conn.execute("INSERT INTO orders VALUES(1,100,'Completed')")
        r=snapshot(self.conn)
        self.assertFalse(r['ready'])
        self.assertEqual(r['financial_audit']['findings'][0]['code'],'paid_without_verified_attempt')
    def test_missing_schema_fails_closed(self):
        self.conn.execute('DROP TABLE refund_requests')
        r=snapshot(self.conn)
        self.assertFalse(r['ready']);self.assertIn('refund_requests',r['missing_tables'])
    def test_read_only(self):
        self.conn.execute("INSERT INTO orders VALUES(1,100,'Awaiting payment')")
        snapshot(self.conn)
        self.assertEqual(self.conn.execute('SELECT status FROM orders').fetchone()[0],'Awaiting payment')

if __name__=='__main__': unittest.main()
