import sqlite3
import unittest
from payment_integrity_audit import audit

class PaymentAuditTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.executescript('''CREATE TABLE orders(id INTEGER PRIMARY KEY,total REAL,status TEXT);
          CREATE TABLE payment_attempts(id INTEGER PRIMARY KEY,order_id INTEGER,amount_cents INTEGER,state TEXT,provider_ref TEXT);
          INSERT INTO orders VALUES(1,20.0,'Paid — fulfillment pending'),(2,10.0,'Awaiting payment');
          INSERT INTO payment_attempts VALUES(1,1,2000,'paid','txn-1'),(2,2,1000,'paid',NULL),
          (3,99,1000,'pending',NULL),(4,1,1999,'pending',NULL);''')
    def tearDown(self):self.c.close()
    def test_clean(self):self.assertEqual(audit(self.c,1)['anomalies'],[])
    def test_missing_reference_and_unpaid_order(self):
        self.assertEqual(set(audit(self.c,1,1)['anomalies'][0]['issues']),{'paid_without_provider_reference','paid_attempt_unpaid_order'})
    def test_missing_order(self):self.assertIn('missing_order',audit(self.c,1,2)['anomalies'][0]['issues'])
    def test_amount_mismatch(self):self.assertIn('order_amount_mismatch',audit(self.c,1,3)['anomalies'][0]['issues'])
    def test_pagination(self):
        self.assertTrue(audit(self.c,2)['has_more']);self.assertFalse(audit(self.c,2,2)['has_more'])
    def test_invalid_pagination(self):
        for n in (0,-1,5001,True):
            with self.assertRaises(ValueError):audit(self.c,n)
if __name__=='__main__':unittest.main()
