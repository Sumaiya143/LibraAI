"""Real refund ledger ↔ entitlement integration regression tests."""
import sqlite3, unittest
from payment_engine import setup as payment_setup, create_attempt, settle_verified
from refund_engine import setup as refund_setup, request_refund, review_refund, confirm_provider_refund
from digital_entitlements import setup as entitlement_setup, has_access

class RefundEntitlementIntegration(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:'); self.c.row_factory=sqlite3.Row
        self.c.executescript("""
            CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,total REAL,status TEXT);
            INSERT INTO orders VALUES(1,7,125.50,'Awaiting payment');
            CREATE TABLE order_items(order_id INTEGER,book_id INTEGER,format TEXT);
            INSERT INTO order_items VALUES(1,10,'ebook');
            CREATE TABLE licensed_documents(book_id INTEGER,access_policy TEXT);
            INSERT INTO licensed_documents VALUES(10,'licensed');
        """)
        payment_setup(self.c); refund_setup(self.c); entitlement_setup(self.c)
        create_attempt(self.c,1,7,'bkash','ref'); settle_verified(self.c,'ref','bkash','pid',12550,'BDT',True,'Completed')
    def tearDown(self): self.c.close()
    def refund(self, amount, reference):
        rid=request_refund(self.c,1,7,amount,'Requested refund for book')
        review_refund(self.c,rid,99,True,admin=True)
        confirm_provider_refund(self.c,rid,reference,verified=True)
        return rid
    def test_partial_refund_preserves_entitlement(self):
        self.refund(2500,'refund-a')
        self.assertTrue(has_access(self.c,7,10))
        self.assertEqual(self.c.execute('SELECT status FROM orders WHERE id=1').fetchone()[0],'Paid — fulfillment pending')
    def test_full_refund_revokes_entitlement(self):
        self.refund(12550,'refund-a')
        self.assertFalse(has_access(self.c,7,10))
        self.assertEqual(self.c.execute('SELECT status FROM orders WHERE id=1').fetchone()[0],'Refunded')
    def test_multiple_partial_refunds_revoke_at_full_total(self):
        self.refund(5000,'refund-a'); self.assertTrue(has_access(self.c,7,10))
        self.refund(7550,'refund-b'); self.assertFalse(has_access(self.c,7,10))
    def test_approval_alone_does_not_revoke(self):
        rid=request_refund(self.c,1,7,12550,'Requested refund for book')
        review_refund(self.c,rid,99,True,admin=True)
        self.assertTrue(has_access(self.c,7,10))
    def test_duplicate_confirmation_remains_idempotent(self):
        rid=self.refund(12550,'refund-a')
        self.assertFalse(confirm_provider_refund(self.c,rid,'refund-a',verified=True))
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM refund_events WHERE event="gateway_refund_verified"').fetchone()[0],1)
if __name__=='__main__': unittest.main()
