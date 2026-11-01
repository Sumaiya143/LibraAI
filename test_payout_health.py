import sqlite3
import unittest
from payout_health import findings

class PayoutHealthTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.executescript('''CREATE TABLE merchant_payouts(id INTEGER PRIMARY KEY,amount TEXT,currency TEXT,status TEXT);
          CREATE TABLE payout_review_events(payout_id INTEGER,new_status TEXT,reference TEXT);''')
    def tearDown(self):
        self.conn.close()
    def codes(self):
        return {f['code'] for f in findings(self.conn)}
    def test_empty(self):
        self.assertEqual(findings(self.conn), [])
    def test_invalid_amount(self):
        self.conn.execute("INSERT INTO merchant_payouts VALUES(1,'NaN','BDT','approved')")
        self.assertIn('INVALID_PAYOUT_AMOUNT_OR_CURRENCY',self.codes())
    def test_invalid_currency(self):
        self.conn.execute("INSERT INTO merchant_payouts VALUES(1,'20.00','USD','approved')")
        self.assertIn('INVALID_PAYOUT_AMOUNT_OR_CURRENCY',self.codes())
    def test_paid_without_event(self):
        self.conn.execute("INSERT INTO merchant_payouts VALUES(1,'20.00','BDT','paid')")
        self.assertIn('PAID_PAYOUT_WITHOUT_REFERENCE_EVENT',self.codes())
    def test_paid_with_event(self):
        self.conn.execute("INSERT INTO merchant_payouts VALUES(1,'20.00','BDT','paid')")
        self.conn.execute("INSERT INTO payout_review_events VALUES(1,'paid','bank-ref-1')")
        self.assertEqual(findings(self.conn), [])
    def test_reused_reference(self):
        self.conn.executemany('INSERT INTO merchant_payouts VALUES(?,?,?,?)',[(1,'20','BDT','paid'),(2,'30','BDT','paid')])
        self.conn.executemany('INSERT INTO payout_review_events VALUES(?,?,?)',[(1,'paid','same'),(2,'paid','same')])
        self.assertIn('REUSED_PAYOUT_REFERENCE',self.codes())
    def test_read_only(self):
        before=self.conn.total_changes
        findings(self.conn)
        self.assertEqual(self.conn.total_changes,before)
