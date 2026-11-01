import sqlite3, unittest
from payment_integrity import reconcile_bkash
from payment_audit import record

class PaymentAuditTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
  self.c.executescript('''CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,amount TEXT,status TEXT);CREATE TABLE bkash_attempts(id INTEGER PRIMARY KEY,order_id INTEGER,user_id INTEGER,payment_id TEXT UNIQUE,status TEXT,trx_id TEXT UNIQUE);CREATE TABLE library(user_id INTEGER,book_id INTEGER,UNIQUE(user_id,book_id));INSERT INTO orders VALUES(1,5,8,'399.00','pending');INSERT INTO orders VALUES(2,5,9,'399.00','pending');INSERT INTO bkash_attempts VALUES(1,1,5,'pay1','initiated',NULL);INSERT INTO bkash_attempts VALUES(2,2,5,'pay2','initiated',NULL);''')
 def tearDown(self):self.c.close()
 def result(self,pid='pay1',trx='tx1',amount='399.00'):
  return {'transactionStatus':'Completed','paymentID':pid,'trxID':trx,'currency':'BDT','amount':amount}
 def events(self):return [dict(x) for x in self.c.execute('SELECT provider,payment_id,order_id,outcome FROM payment_audit_events ORDER BY id')]
 def test_success_audited(self):
  self.assertEqual(reconcile_bkash(self.c,'pay1',self.result()),'confirmed');self.assertEqual(self.events()[0]['outcome'],'confirmed')
 def test_repeat_audited_no_duplicate_delivery(self):
  reconcile_bkash(self.c,'pay1',self.result());reconcile_bkash(self.c,'pay1',self.result());self.assertEqual(len(self.events()),2);self.assertEqual(self.c.execute('SELECT count(*) FROM library').fetchone()[0],1)
 def test_mismatch_audited(self):
  self.assertEqual(reconcile_bkash(self.c,'pay1',self.result(amount='1.00')),'mismatch');self.assertEqual(self.events()[0]['outcome'],'mismatch')
 def test_unknown_audited(self):
  self.assertEqual(reconcile_bkash(self.c,'missing',self.result()),'unknown');self.assertIsNone(self.events()[0]['order_id'])
 def test_replay_audited(self):
  reconcile_bkash(self.c,'pay1',self.result());self.assertEqual(reconcile_bkash(self.c,'pay2',self.result('pay2')),'replayed');self.assertEqual(self.events()[-1]['outcome'],'replayed')
 def test_no_secrets_stored(self):
  reconcile_bkash(self.c,'pay1',self.result());self.assertEqual(set(self.events()[0]),{'provider','payment_id','order_id','outcome'})
if __name__=='__main__':unittest.main()
