import sqlite3
import unittest
from commerce_reconciliation import report


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.executescript('''
          CREATE TABLE subscription_invoices(status TEXT, expires_at TEXT);
          CREATE TABLE bkash_attempts(status TEXT, trx_id TEXT);
          CREATE TABLE orders(status TEXT);
          CREATE TABLE merchant_payouts(status TEXT);
          INSERT INTO subscription_invoices VALUES ('unpaid','2000-01-01');
          INSERT INTO subscription_invoices VALUES ('paid','2000-01-01');
          INSERT INTO bkash_attempts VALUES ('validated','abc');
          INSERT INTO orders VALUES ('pending');
          INSERT INTO merchant_payouts VALUES ('approved');
        ''')
    def tearDown(self):
        self.conn.close()
    def test_counts_and_overdue(self):
        result=report(self.conn)
        self.assertEqual(result['invoices'], {'unpaid':1,'paid':1})
        self.assertEqual(result['overdue_unpaid_invoices'],1)
        self.assertEqual(result['orders']['pending'],1)
    def test_read_only(self):
        before=self.conn.total_changes
        report(self.conn)
        self.assertEqual(self.conn.total_changes,before)
    def test_missing_tables(self):
        with sqlite3.connect(':memory:') as c:
            result=report(c)
            self.assertEqual(len(result['warnings']),4)
    def test_duplicate_transaction_warning(self):
        self.conn.execute("INSERT INTO bkash_attempts VALUES ('validated','abc')")
        self.assertEqual(report(self.conn)['duplicate_bkash_transaction_ids'],1)
