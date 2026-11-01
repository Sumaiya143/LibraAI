import sqlite3
import unittest
from refund_batch_audit import audit_all_refunds

class BatchRefundAuditTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''
          CREATE TABLE orders (id INTEGER PRIMARY KEY);
          CREATE TABLE payment_attempts (id INTEGER PRIMARY KEY,order_id INTEGER,amount_cents INTEGER,state TEXT);
          CREATE TABLE refund_requests (id INTEGER PRIMARY KEY,order_id INTEGER,attempt_id INTEGER,amount_cents INTEGER,state TEXT,provider_ref TEXT);
          INSERT INTO orders VALUES(1);
          INSERT INTO payment_attempts VALUES(1,1,1000,'paid');
          INSERT INTO refund_requests VALUES(1,1,1,100,'refunded','ref1');
          INSERT INTO refund_requests VALUES(2,1,1,100,'refunded',NULL);
          INSERT INTO refund_requests VALUES(3,1,1,100,'requested',NULL);
        ''')
    def tearDown(self): self.db.close()
    def test_multiple_pages(self):
        r = audit_all_refunds(self.db, page_size=1)
        self.assertEqual(r['checked'],3)
        self.assertEqual(r['issue_count'],1)
        self.assertEqual(r['issue_types'],{'confirmed_refund_missing_provider_reference':1})
        self.assertFalse(r['truncated'])
    def test_bounded_truncation(self):
        r = audit_all_refunds(self.db, page_size=1,max_records=2)
        self.assertEqual(r['checked'],2)
        self.assertTrue(r['truncated'])
    def test_summary_only(self):
        r = audit_all_refunds(self.db, page_size=2,exceptions_only=True)
        self.assertNotIn('issues',r)
        self.assertEqual(r['issue_count'],1)
    def test_bad_limits(self):
        for value in (0,501,True):
            with self.assertRaises(ValueError): audit_all_refunds(self.db,page_size=value)
        for value in (0,100001,False):
            with self.assertRaises(ValueError): audit_all_refunds(self.db,max_records=value)
    def test_read_only(self):
        audit_all_refunds(self.db,page_size=1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM refund_requests').fetchone()[0],3)
