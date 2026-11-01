import sqlite3
import unittest
from payment_engine import setup as payment_setup, create_attempt, mark_pending, settle_verified
from refund_engine import setup, request_refund, review_refund, RefundError

class ItemRefundAllocationTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.row_factory=sqlite3.Row
        self.db.execute('CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,total REAL,status TEXT)')
        self.db.execute("INSERT INTO orders VALUES(1,7,100.0,'Awaiting payment')")
        self.db.execute('''CREATE TABLE order_items(id INTEGER PRIMARY KEY,order_id INTEGER,book_id INTEGER,
            unit_price_cents INTEGER,quantity INTEGER,format TEXT)''')
        self.db.executemany('INSERT INTO order_items VALUES(?,?,?,?,?,?)',[(11,1,5,2000,2,'physical'),(12,1,6,6000,1,'ebook'),(13,2,7,500,1,'ebook')])
        self.db.execute('CREATE TABLE licensed_documents(book_id INTEGER,access_policy TEXT)')
        payment_setup(self.db)
        setup(self.db)
        create_attempt(self.db,1,7,'bkash','item-ref')
        mark_pending(self.db,'item-ref','provider-item')
        settle_verified(self.db,'item-ref','bkash','provider-item',10000,'BDT',True,'Completed')
    def tearDown(self): self.db.close()
    def request(self, amount, item=11):
        return request_refund(self.db,1,7,amount,'Item return requested',item_id=item)
    def test_item_request_is_linked(self):
        rid=self.request(2500)
        row=self.db.execute('SELECT order_item_id,amount_cents FROM refund_item_allocations WHERE refund_id=?',(rid,)).fetchone()
        self.assertEqual(tuple(row),(11,2500))
    def test_reject_foreign_item(self):
        with self.assertRaisesRegex(RefundError,'not found'):self.request(100,13)
    def test_line_amount_cap(self):
        self.request(3500)
        with self.assertRaisesRegex(RefundError,'item balance'):self.request(501)
        self.assertIsInstance(self.request(500),int)
    def test_rejected_request_releases_item_balance(self):
        rid=self.request(4000)
        review_refund(self.db,rid,99,False,admin=True)
        self.assertIsInstance(self.request(4000),int)
    def test_no_cross_order_or_boolean_id(self):
        for value in (True,0,-1,'11'):
            with self.subTest(value=value),self.assertRaises(RefundError):self.request(100,value)
    def test_payment_cap_still_applies(self):
        request_refund(self.db,1,7,9000,'Order adjustment')
        with self.assertRaisesRegex(RefundError,'paid balance'):self.request(1001)
    def test_legacy_order_refund_works(self):
        rid=request_refund(self.db,1,7,1000,'Order adjustment')
        self.assertIsNone(self.db.execute('SELECT order_item_id FROM refund_item_allocations WHERE refund_id=?',(rid,)).fetchone())
    def test_invalid_item_price(self):
        self.db.execute('UPDATE order_items SET unit_price_cents=-1 WHERE id=11');self.db.commit()
        with self.assertRaisesRegex(RefundError,'price snapshot'):self.request(100)

if __name__=='__main__':unittest.main()
