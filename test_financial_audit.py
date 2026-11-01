import sqlite3
import unittest
from financial_audit import audit

class FinancialAuditTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''
        CREATE TABLE orders(id INTEGER PRIMARY KEY,total REAL,status TEXT);
        CREATE TABLE payment_attempts(id INTEGER PRIMARY KEY,order_id INTEGER,state TEXT,amount_cents INTEGER,currency TEXT);
        CREATE TABLE digital_entitlements(id INTEGER PRIMARY KEY,order_id INTEGER);
        ''')
    def tearDown(self): self.db.close()
    def test_empty_is_clean(self): self.assertTrue(audit(self.db)['ok'])
    def test_verified_paid_is_clean(self):
        self.db.execute("INSERT INTO orders VALUES(1,100,'Completed')")
        self.db.execute("INSERT INTO payment_attempts VALUES(1,1,'paid',10000,'BDT')")
        self.assertTrue(audit(self.db)['ok'])
    def test_paid_without_payment(self):
        self.db.execute("INSERT INTO orders VALUES(1,100,'Completed')")
        self.assertIn('paid_without_verified_attempt',[x['code'] for x in audit(self.db)['findings']])
    def test_mismatched_amount(self):
        self.db.execute("INSERT INTO orders VALUES(1,100,'Completed')")
        self.db.execute("INSERT INTO payment_attempts VALUES(1,1,'paid',9900,'BDT')")
        self.assertIn('payment_amount_mismatch',[x['code'] for x in audit(self.db)['findings']])
    def test_paid_cancelled_order(self):
        self.db.execute("INSERT INTO orders VALUES(1,100,'Cancelled')")
        self.db.execute("INSERT INTO payment_attempts VALUES(1,1,'paid',10000,'BDT')")
        self.assertIn('paid_attempt_unpaid_order',[x['code'] for x in audit(self.db)['findings']])
    def test_unpaid_entitlement(self):
        self.db.execute("INSERT INTO orders VALUES(1,100,'Awaiting payment')")
        self.db.execute('INSERT INTO digital_entitlements VALUES(1,1)')
        self.assertIn('entitlement_without_paid_order',[x['code'] for x in audit(self.db)['findings']])
    def test_missing_schema_fails_closed(self):
        self.db.execute('DROP TABLE payment_attempts')
        self.assertFalse(audit(self.db)['ok'])
if __name__=='__main__': unittest.main()
