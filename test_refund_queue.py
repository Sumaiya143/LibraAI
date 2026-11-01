import sqlite3
import unittest
from refund_queue import list_refund_queue
from refund_engine import RefundError, setup as refund_setup
from payment_engine import setup as payment_setup

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.execute('CREATE TABLE orders(id INTEGER PRIMARY KEY, user_id INTEGER, total REAL, status TEXT)')
        payment_setup(self.db)
        refund_setup(self.db)
        self.db.execute("INSERT INTO orders VALUES(1,7,100,'Paid')")
        self.db.execute("INSERT INTO payment_attempts(order_id,provider,merchant_ref,amount_cents,state,created,updated) VALUES(1,'bkash','merchant-ref',10000,'paid','2026-01-01','2026-01-01')")
        for i, state in enumerate(('requested','approved','requested','refunded','rejected')):
            self.db.execute("INSERT INTO refund_requests(attempt_id,order_id,amount_cents,reason,state,created,updated) VALUES(1,1,100,'reason',?,?,?)", (state, '2026-01-01', '2026-01-01'))
        self.db.commit()
    def tearDown(self): self.db.close()
    def test_default_only_pending(self):
        report = list_refund_queue(self.db)
        self.assertEqual(report['total'],2)
        self.assertEqual([x['id'] for x in report['items']],[1,3])
        self.assertNotIn('reason',report['items'][0])
        self.assertNotIn('merchant_ref',report['items'][0])
    def test_pages_and_filter(self):
        first = list_refund_queue(self.db,state='all',limit=2)
        second = list_refund_queue(self.db,state='all',limit=2,offset=2)
        self.assertEqual(first['total'],5)
        self.assertTrue(first['has_more'])
        self.assertEqual([x['id'] for x in second['items']],[3,4])
        self.assertEqual(list_refund_queue(self.db,state='refunded')['total'],1)
    def test_invalid_input(self):
        for kwargs in ({'state':'paid'},{'limit':0},{'limit':101},{'limit':True},{'offset':-1},{'offset':False},{'offset':1000001}):
            with self.subTest(kwargs=kwargs),self.assertRaises(RefundError):
                list_refund_queue(self.db,**kwargs)
    def test_empty_page(self):
        result=list_refund_queue(self.db,offset=100)
        self.assertEqual(result['items'],[])
        self.assertFalse(result['has_more'])

if __name__ == '__main__': unittest.main()
