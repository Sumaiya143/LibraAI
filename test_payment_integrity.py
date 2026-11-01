import unittest, sqlite3
from payment_integrity import canonical_amount,verify_bkash_result,reconcile_bkash

class PaymentIntegrityTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
  self.c.executescript('''CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,amount TEXT,status TEXT);CREATE TABLE bkash_attempts(id INTEGER PRIMARY KEY,order_id INTEGER,user_id INTEGER,payment_id TEXT UNIQUE,status TEXT,trx_id TEXT UNIQUE);CREATE TABLE library(user_id INTEGER,book_id INTEGER,UNIQUE(user_id,book_id));INSERT INTO orders VALUES(1,5,8,'399.00','pending');INSERT INTO orders VALUES(2,5,9,'399.00','pending');INSERT INTO bkash_attempts VALUES(1,1,5,'pay1','initiated',NULL);INSERT INTO bkash_attempts VALUES(2,2,5,'pay2','initiated',NULL);''')
 def tearDown(self):self.c.close()
 def result(self,payment='pay1',trx='tx1',amount='399.00'):
  return {'transactionStatus':'Completed','paymentID':payment,'trxID':trx,'currency':'BDT','amount':amount}
 def test_success_and_idempotence(self):
  self.assertEqual(reconcile_bkash(self.c,'pay1',self.result()),'confirmed')
  self.assertEqual(reconcile_bkash(self.c,'pay1',self.result()),'confirmed')
  self.assertEqual(self.c.execute('SELECT count(*) FROM library').fetchone()[0],1)
 def test_replay_rejected(self):
  reconcile_bkash(self.c,'pay1',self.result())
  self.assertEqual(reconcile_bkash(self.c,'pay2',self.result('pay2')),'replayed')
  self.assertEqual(self.c.execute('SELECT status FROM orders WHERE id=2').fetchone()[0],'pending')
 def test_mismatched_amount(self):
  self.assertEqual(reconcile_bkash(self.c,'pay1',self.result(amount='399.01')),'mismatch')
 def test_missing_provider_transaction_id(self):
  result=self.result();del result['trxID']
  self.assertFalse(verify_bkash_result(result,'pay1',{'amount':'399.00'}))
 def test_invalid_amounts(self):
  for amount in ('NaN','Infinity','0','-1','1.001',None):
   with self.subTest(amount=amount):
    with self.assertRaises(ValueError):canonical_amount(amount)
 def test_wrong_payment_id(self):
  self.assertEqual(reconcile_bkash(self.c,'pay1',self.result('different')),'mismatch')

if __name__=='__main__':unittest.main()
