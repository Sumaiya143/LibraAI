"""Offline integration: mixed checkout -> verified payment -> item refund -> entitlement."""
import sqlite3
import unittest
from commerce_engine import setup as commerce_setup, place_sandbox_order
from payment_engine import setup as payment_setup, create_attempt, settle_verified, PaymentError
from digital_entitlements import setup as entitlement_setup, has_access
from refund_engine import setup as refund_setup, request_refund, review_refund, confirm_provider_refund

class MixedCartPaymentFulfillmentE2E(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.row_factory=sqlite3.Row
        self.c.executescript('''
        CREATE TABLE books(id INTEGER PRIMARY KEY,title TEXT,price REAL,stock INTEGER);
        CREATE TABLE cart(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,qty INTEGER,format TEXT);
        CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,total REAL,status TEXT,address TEXT,created TEXT);
        CREATE TABLE licensed_documents(id INTEGER PRIMARY KEY,book_id INTEGER,access_policy TEXT);
        INSERT INTO books VALUES(1,'Printed',100,5),(2,'Licensed EPUB',50,0),(3,'Second EPUB',25,0);
        INSERT INTO licensed_documents VALUES(1,2,'licensed'),(2,3,'licensed');
        INSERT INTO cart VALUES(1,7,1,2,'Print'),(2,7,2,1,'eBook'),(3,7,3,1,'eBook');
        ''')
        commerce_setup(self.c);payment_setup(self.c);refund_setup(self.c);entitlement_setup(self.c)
    def tearDown(self): self.c.close()
    def checkout(self):
        oid,created=place_sandbox_order(self.c,7,'mixed-cart-key-001',address='Delivery address')
        self.assertTrue(created)
        self.assertEqual(self.c.execute('SELECT stock FROM books WHERE id=1').fetchone()[0],3)
        self.assertEqual(self.c.execute('SELECT stock FROM books WHERE id=2').fetchone()[0],0)
        self.assertEqual(self.c.execute('SELECT total_cents FROM order_amounts WHERE order_id=?',(oid,)).fetchone()[0],27500)
        self.assertEqual(self.c.execute('SELECT SUM(line_total_cents) FROM order_items WHERE order_id=?',(oid,)).fetchone()[0],27500)
        return oid
    def pay(self,oid):
        create_attempt(self.c,oid,7,'bkash','mixed-merchant-1')
        return settle_verified(self.c,'mixed-merchant-1','bkash','mixed-gateway-1',27500,'BDT',True,'Completed')
    def test_mixed_checkout_payment_and_item_refund(self):
        oid=self.checkout()
        self.assertFalse(has_access(self.c,7,2))
        with self.assertRaises(PaymentError):
            settle_verified(self.c,'mixed-merchant-1','bkash','mixed-gateway-1',27500,'BDT',True,'Completed')
        self.assertTrue(self.pay(oid))
        self.assertTrue(has_access(self.c,7,2));self.assertTrue(has_access(self.c,7,3))
        self.assertFalse(has_access(self.c,8,2));self.assertFalse(has_access(self.c,7,1))
        self.assertFalse(self.pay_repeat())
        line=self.c.execute("SELECT id FROM order_items WHERE order_id=? AND book_id=2 AND format='eBook'",(oid,)).fetchone()[0]
        rid=request_refund(self.c,oid,7,5000,'Digital title refund',item_id=line)
        review_refund(self.c,rid,99,True,admin=True)
        self.assertTrue(has_access(self.c,7,2))
        confirm_provider_refund(self.c,rid,'refund-mixed-002',verified=True)
        self.assertFalse(has_access(self.c,7,2))
        self.assertTrue(has_access(self.c,7,3))
        self.assertEqual(self.c.execute('SELECT stock FROM books WHERE id=1').fetchone()[0],3)
    def pay_repeat(self):
        return settle_verified(self.c,'mixed-merchant-1','bkash','mixed-gateway-1',27500,'BDT',True,'Completed')
    def test_failed_settlement_does_not_grant_or_change_stock(self):
        oid=self.checkout()
        create_attempt(self.c,oid,7,'bkash','mixed-merchant-1')
        with self.assertRaises(PaymentError):
            settle_verified(self.c,'mixed-merchant-1','bkash','mixed-gateway-1',27499,'BDT',True,'Completed')
        self.assertFalse(has_access(self.c,7,2))
        self.assertEqual(self.c.execute('SELECT stock FROM books WHERE id=1').fetchone()[0],3)
    def test_tampered_line_amount_blocks_payment_initiation(self):
        oid=self.checkout()
        self.c.execute('UPDATE order_items SET line_total_cents=line_total_cents+1 WHERE order_id=? AND book_id=2',(oid,))
        self.c.commit()
        with self.assertRaisesRegex(PaymentError,'allocation mismatch'):
            create_attempt(self.c,oid,7,'bkash','mixed-merchant-1')
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM payment_attempts').fetchone()[0],0)
    def test_tampered_line_amount_blocks_settlement(self):
        oid=self.checkout()
        create_attempt(self.c,oid,7,'bkash','mixed-merchant-1')
        self.c.execute('UPDATE order_items SET line_total_cents=line_total_cents-1 WHERE order_id=? AND book_id=2',(oid,))
        self.c.commit()
        with self.assertRaisesRegex(PaymentError,'allocation mismatch'):
            settle_verified(self.c,'mixed-merchant-1','bkash','mixed-gateway-1',27500,'BDT',True,'Completed')
        self.assertFalse(has_access(self.c,7,2))
        self.assertEqual(self.c.execute("SELECT state FROM payment_attempts WHERE merchant_ref='mixed-merchant-1'").fetchone()[0],'created')
    def test_idempotent_checkout_does_not_reserve_stock_twice(self):
        oid=self.checkout()
        again,created=place_sandbox_order(self.c,7,'mixed-cart-key-001',address='Delivery address')
        self.assertFalse(created);self.assertEqual(again,oid)
        self.assertEqual(self.c.execute('SELECT stock FROM books WHERE id=1').fetchone()[0],3)
if __name__=='__main__':unittest.main()
