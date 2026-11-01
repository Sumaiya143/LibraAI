import sqlite3
import unittest
from payment_batch_audit import scan


class BatchAuditTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''CREATE TABLE orders(id INTEGER PRIMARY KEY,total REAL,status TEXT);
          CREATE TABLE payment_attempts(id INTEGER PRIMARY KEY,order_id INTEGER,amount_cents INTEGER,state TEXT,provider_ref TEXT);
          INSERT INTO orders VALUES(1,20.0,'Paid — fulfillment pending'),(2,10.0,'Awaiting payment');
          INSERT INTO payment_attempts VALUES(1,1,2000,'paid','txn-1'),(2,2,1000,'paid',NULL),
          (3,99,1000,'pending',NULL),(4,1,1999,'pending',NULL);''')

    def tearDown(self):
        self.db.close()

    def test_full_scan_across_pages(self):
        r = scan(self.db, page_size=1)
        self.assertEqual(r['checked'], 4)
        self.assertFalse(r['incomplete'])
        self.assertEqual(len(r['anomalies']), 3)
        self.assertEqual(r['anomaly_counts']['missing_order'], 1)
        self.assertEqual(r['anomaly_counts']['paid_without_provider_reference'], 1)

    def test_exact_limit_is_complete(self):
        r = scan(self.db, page_size=2, max_records=4)
        self.assertFalse(r['incomplete'])

    def test_truncated_scan_is_flagged(self):
        r = scan(self.db, page_size=2, max_records=3)
        self.assertEqual(r['checked'], 3)
        self.assertTrue(r['incomplete'])

    def test_summary_only(self):
        r = scan(self.db, page_size=2, include_anomalies=False)
        self.assertEqual(r['anomalies'], [])
        self.assertGreater(r['anomaly_total'], 0)

    def test_invalid_bounds(self):
        for n in (0, -1, True, 5001):
            with self.assertRaises(ValueError):
                scan(self.db, page_size=n)
        for n in (0, -1, True, 1000001):
            with self.assertRaises(ValueError):
                scan(self.db, max_records=n)

    def test_no_mutation(self):
        before = self.db.execute('SELECT * FROM payment_attempts').fetchall()
        scan(self.db, page_size=1)
        self.assertEqual(before, self.db.execute('SELECT * FROM payment_attempts').fetchall())


if __name__ == '__main__':
    unittest.main()
