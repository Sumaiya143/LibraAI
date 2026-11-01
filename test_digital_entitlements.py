import sqlite3, unittest
from payment_engine import setup as payment_setup, create_attempt, settle_verified
from digital_entitlements import setup, has_access

class EntitlementTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.c.executescript('''CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,total REAL,status TEXT);
        INSERT INTO orders VALUES(1,7,125.50,'Awaiting payment');
        CREATE TABLE order_items(id INTEGER PRIMARY KEY,order_id INTEGER,book_id INTEGER,format TEXT);
        INSERT INTO order_items VALUES(1,1,10,'eBook');
        INSERT INTO order_items VALUES(2,1,11,'Print');
        INSERT INTO order_items VALUES(3,1,12,'eBook');
        CREATE TABLE licensed_documents(id INTEGER PRIMARY KEY,book_id INTEGER,access_policy TEXT);
        INSERT INTO licensed_documents VALUES(1,10,'licensed');
        INSERT INTO licensed_documents VALUES(2,11,'licensed');
        INSERT INTO licensed_documents VALUES(3,12,'sample');''')
        payment_setup(self.c);setup(self.c)
    def tearDown(self): self.c.close()
    def test_verified_payment_grants_only_licensed_ebook(self):
        create_attempt(self.c,1,7,'bkash','ref')
        self.assertFalse(has_access(self.c,7,10))
        settle_verified(self.c,'ref','bkash','pid',12550,'BDT',True,'Completed')
        self.assertTrue(has_access(self.c,7,10))
        self.assertFalse(has_access(self.c,7,11))
        self.assertFalse(has_access(self.c,7,12))
        self.assertFalse(has_access(self.c,8,10))
    def test_repeat_callback_does_not_duplicate_grant(self):
        create_attempt(self.c,1,7,'bkash','ref')
        settle_verified(self.c,'ref','bkash','pid',12550,'BDT',True,'Completed')
        self.assertFalse(settle_verified(self.c,'ref','bkash','pid',12550,'BDT',True,'Completed'))
        self.assertEqual(self.c.execute('SELECT count(*) FROM digital_entitlements').fetchone()[0],1)
    def test_refund_or_cancellation_blocks_access(self):
        create_attempt(self.c,1,7,'bkash','ref')
        settle_verified(self.c,'ref','bkash','pid',12550,'BDT',True,'Completed')
        self.c.execute("UPDATE orders SET status='Refunded' WHERE id=1")
        self.assertFalse(has_access(self.c,7,10))
    def test_invalid_settlement_cannot_grant(self):
        create_attempt(self.c,1,7,'bkash','ref')
        with self.assertRaises(ValueError):
            settle_verified(self.c,'ref','bkash','pid',12549,'BDT',True,'Completed')
        self.assertFalse(has_access(self.c,7,10))

if __name__=='__main__': unittest.main()
