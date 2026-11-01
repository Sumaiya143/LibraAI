"""Regression: discounted line allocations must control entitlement revocation."""
import sqlite3
import unittest
from payment_engine import setup as payment_setup, create_attempt, settle_verified
from refund_engine import setup as refund_setup, request_refund, review_refund, confirm_provider_refund
from digital_entitlements import setup as entitlement_setup, has_access

class DiscountedEbookEntitlementTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(':memory:')
        self.c.row_factory = sqlite3.Row
        self.c.executescript('''
        CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,total REAL,status TEXT);
        INSERT INTO orders VALUES(1,7,90,'Awaiting payment');
        CREATE TABLE order_items(id INTEGER PRIMARY KEY,order_id INTEGER,book_id INTEGER,
          format TEXT,unit_price_cents INTEGER,quantity INTEGER,line_total_cents INTEGER);
        INSERT INTO order_items VALUES(11,1,10,'ebook',5000,1,4500);
        INSERT INTO order_items VALUES(12,1,20,'ebook',5000,1,4500);
        CREATE TABLE licensed_documents(book_id INTEGER,access_policy TEXT);
        INSERT INTO licensed_documents VALUES(10,'licensed'),(20,'licensed');
        ''')
        payment_setup(self.c); refund_setup(self.c); entitlement_setup(self.c)
        create_attempt(self.c,1,7,'bkash','discount-pay')
        settle_verified(self.c,'discount-pay','bkash','paid-ref',9000,'BDT',True,'Completed')
    def tearDown(self): self.c.close()
    def refund(self, item, amount, ref):
        rid = request_refund(self.c,1,7,amount,'Discounted item',item_id=item)
        review_refund(self.c,rid,99,True,admin=True)
        confirm_provider_refund(self.c,rid,ref,verified=True)
    def test_full_discounted_line_refund_revokes_only_its_book(self):
        self.refund(11,4500,'refund-book10')
        self.assertFalse(has_access(self.c,7,10))
        self.assertTrue(has_access(self.c,7,20))
    def test_partial_discounted_refund_preserves_access(self):
        self.refund(11,2000,'refund-part-a')
        self.assertTrue(has_access(self.c,7,10))
        self.refund(11,2500,'refund-part-b')
        self.assertFalse(has_access(self.c,7,10))
    def test_other_book_refund_preserves_access(self):
        self.refund(12,4500,'refund-book20')
        self.assertTrue(has_access(self.c,7,10))
        self.assertFalse(has_access(self.c,7,20))

if __name__ == '__main__': unittest.main()
