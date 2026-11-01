import sqlite3
import unittest
from commerce_engine import setup as commerce_setup, place_sandbox_order
from payment_engine import setup as payment_setup, create_attempt, mark_pending, settle_verified, PaymentError

class ExactLedgerTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(':memory:')
        self.c.row_factory = sqlite3.Row
        self.c.executescript("""CREATE TABLE books(id INTEGER PRIMARY KEY,title TEXT,price REAL,stock INTEGER);
        CREATE TABLE cart(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,qty INTEGER,format TEXT);
        CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,total REAL,status TEXT,address TEXT,created TEXT);""")
        commerce_setup(self.c)
        payment_setup(self.c)
        self.c.execute("INSERT INTO books VALUES(1,'Book',10.25,5)")
        self.c.execute("INSERT INTO cart VALUES(1,7,1,2,'Print')")
        self.c.commit()
        self.order_id, _ = place_sandbox_order(self.c, 7, 'request-ledger-123')

    def tearDown(self): self.c.close()

    def test_checkout_stores_exact_integer_minor_units(self):
        row=self.c.execute('SELECT total_cents,currency FROM order_amounts WHERE order_id=?',(self.order_id,)).fetchone()
        self.assertEqual(tuple(row), (2050,'BDT'))

    def test_payment_attempt_uses_exact_ledger(self):
        attempt,_=create_attempt(self.c,self.order_id,7,'bkash','merchant-ledger-1')
        self.assertEqual(attempt['amount_cents'],2050)

    def test_ledger_tampering_blocks_new_attempt(self):
        self.c.execute('UPDATE order_amounts SET total_cents=2051 WHERE order_id=?',(self.order_id,))
        self.c.commit()
        with self.assertRaisesRegex(PaymentError,'ledger mismatch'):
            create_attempt(self.c,self.order_id,7,'bkash','merchant-ledger-2')

    def test_ledger_tampering_blocks_settlement(self):
        create_attempt(self.c,self.order_id,7,'bkash','merchant-ledger-settle')
        mark_pending(self.c,'merchant-ledger-settle','provider-settle')
        self.c.execute('UPDATE order_amounts SET total_cents=2051 WHERE order_id=?',(self.order_id,))
        self.c.commit()
        with self.assertRaisesRegex(PaymentError,'ledger mismatch'):
            settle_verified(self.c,'merchant-ledger-settle','bkash','provider-settle',2050,'BDT',True,'success')
        self.assertEqual(self.c.execute('SELECT state FROM payment_attempts WHERE merchant_ref=?',('merchant-ledger-settle',)).fetchone()[0],'pending')

    def test_untampered_settlement_reaches_fulfillment(self):
        create_attempt(self.c,self.order_id,7,'bkash','merchant-ledger-success')
        mark_pending(self.c,'merchant-ledger-success','provider-success')
        self.assertTrue(settle_verified(self.c,'merchant-ledger-success','bkash','provider-success',2050,'BDT',True,'success'))
        self.assertEqual(self.c.execute('SELECT status FROM orders WHERE id=?',(self.order_id,)).fetchone()[0],'Paid — fulfillment pending')

    def test_ledger_tampering_blocks_session_launch(self):
        create_attempt(self.c,self.order_id,7,'bkash','merchant-ledger-3')
        self.c.execute('UPDATE order_amounts SET total_cents=2051 WHERE order_id=?',(self.order_id,))
        self.c.commit()
        with self.assertRaisesRegex(PaymentError,'ledger mismatch'):
            mark_pending(self.c,'merchant-ledger-3','provider-session-3')

if __name__ == '__main__': unittest.main()
