import sqlite3
import unittest
from refund_integrity_audit import audit_refunds

class RefundIntegrityCommercialTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript("""
            CREATE TABLE orders(id INTEGER PRIMARY KEY);
            CREATE TABLE payment_attempts(id INTEGER PRIMARY KEY, order_id INTEGER, amount_cents INTEGER, state TEXT);
            CREATE TABLE refund_requests(id INTEGER PRIMARY KEY, order_id INTEGER, attempt_id INTEGER,
                amount_cents INTEGER, state TEXT, provider_ref TEXT);
            INSERT INTO orders VALUES(1);
            INSERT INTO payment_attempts VALUES(1,1,2000,'paid');
        """)
    def tearDown(self):
        self.db.close()
    def test_duplicate_confirmed_provider_reference_detected(self):
        self.db.executescript("""
            INSERT INTO refund_requests VALUES(1,1,1,100,'refunded','same');
            INSERT INTO refund_requests VALUES(2,1,1,100,'refunded','same');
        """)
        result = audit_refunds(self.db)
        self.assertEqual(result['issue_count'],2)
        self.assertTrue(all('duplicate_confirmed_provider_reference' in x['issues'] for x in result['issues']))
    def test_distinct_confirmed_references_not_flagged(self):
        self.db.executescript("""
            INSERT INTO refund_requests VALUES(1,1,1,100,'refunded','one');
            INSERT INTO refund_requests VALUES(2,1,1,100,'refunded','two');
        """)
        self.assertEqual(audit_refunds(self.db)['issue_count'],0)
    def test_refunded_unpaid_attempt_detected(self):
        self.db.execute("UPDATE payment_attempts SET state='pending' WHERE id=1")
        self.db.execute("INSERT INTO refund_requests VALUES(1,1,1,100,'refunded','one')")
        issues = audit_refunds(self.db)['issues'][0]['issues']
        self.assertIn('refunded_against_unpaid_attempt',issues)
    def test_requested_duplicate_reference_does_not_trigger_confirmed_duplicate(self):
        self.db.executescript("""
            INSERT INTO refund_requests VALUES(1,1,1,100,'refunded','one');
            INSERT INTO refund_requests VALUES(2,1,1,100,'requested','one');
        """)
        issues = audit_refunds(self.db)['issues']
        self.assertNotIn('duplicate_confirmed_provider_reference',issues[0]['issues'])
