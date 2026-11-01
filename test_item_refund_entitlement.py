import sqlite3
import unittest
from payment_engine import setup as payment_setup, create_attempt, settle_verified
from refund_engine import setup as refund_setup, request_refund, review_refund, confirm_provider_refund
from digital_entitlements import setup as entitlement_setup, has_access

class ItemRefundEntitlementTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.c.executescript('''CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,total REAL,status TEXT);
        INSERT INTO orders VALUES(1,7,100,'Awaiting payment');
        CREATE TABLE order_items(id INTEGER PRIMARY KEY,order_id INTEGER,book_id INTEGER,format TEXT,unit_price_cents INTEGER,quantity INTEGER);
        INSERT INTO order_items VALUES(11,1,10,'ebook',3000,1);
        INSERT INTO order_items VALUES(12,1,20,'ebook',4000,1);
        INSERT INTO order_items VALUES(13,1,30,'print',3000,1);
        CREATE TABLE licensed_documents(book_id INTEGER,access_policy TEXT);
        INSERT INTO licensed_documents VALUES(10,'licensed'),(20,'licensed'),(30,'licensed');''')
        payment_setup(self.c);refund_setup(self.c);entitlement_setup(self.c)
        create_attempt(self.c,1,7,'bkash','item-pay')
        settle_verified(self.c,'item-pay','bkash','payment-id',10000,'BDT',True,'Completed')
    def tearDown(self):self.c.close()
    def refund(self,item,amount,ref,confirm=True):
        rid=request_refund(self.c,1,7,amount,'Book refund requested',item_id=item)
        review_refund(self.c,rid,99,True,admin=True)
        if confirm:confirm_provider_refund(self.c,rid,ref,verified=True)
        return rid
    def test_one_refunded_ebook_does_not_revoke_other_ebook(self):
        self.refund(11,3000,'ref-item-11')
        self.assertFalse(has_access(self.c,7,10))
        self.assertTrue(has_access(self.c,7,20))
    def test_partial_item_refund_preserves_access(self):
        self.refund(11,1000,'ref-part-1')
        self.assertTrue(has_access(self.c,7,10))
        self.refund(11,2000,'ref-part-2')
        self.assertFalse(has_access(self.c,7,10))
    def test_approval_alone_does_not_revoke(self):
        self.refund(11,3000,'unused-ref',confirm=False)
        self.assertTrue(has_access(self.c,7,10))
    def test_print_refund_does_not_revoke_ebook(self):
        self.refund(13,3000,'ref-print')
        self.assertTrue(has_access(self.c,7,10))
    def test_invalid_user_and_book_rejected(self):
        self.assertFalse(has_access(self.c,True,10))
        self.assertFalse(has_access(self.c,7,True))
if __name__=='__main__':unittest.main()
