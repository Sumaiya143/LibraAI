import sqlite3,unittest
from ssl_payment_integrity import reconcile_sslcommerz

class TestSSLIntegrity(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
  self.c.executescript('''CREATE TABLE payment_attempts(id INTEGER PRIMARY KEY,order_id INTEGER,transaction_id TEXT,provider TEXT,status TEXT,validation_id TEXT);CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,amount TEXT,status TEXT);CREATE TABLE library(user_id INTEGER,book_id INTEGER,UNIQUE(user_id,book_id));CREATE TABLE payment_events(transaction_id TEXT,event TEXT);INSERT INTO orders VALUES(1,2,3,'120.00','pending');INSERT INTO payment_attempts VALUES(1,1,'TX1','sslcommerz','initiated',NULL);''')
 def tearDown(self):self.c.close()
 def payload(self,**kw):return dict({'status':'VALID','tran_id':'TX1','currency':'BDT','amount':'120.00'},**kw)
 def test_success_and_duplicate(self):
  self.assertEqual(reconcile_sslcommerz(self.c,'TX1','VAL1',self.payload()),'confirmed')
  self.assertEqual(reconcile_sslcommerz(self.c,'TX1','VAL1',self.payload()),'duplicate')
  self.assertEqual(self.c.execute('SELECT count(*) FROM library').fetchone()[0],1)
  self.assertEqual(self.c.execute('SELECT count(*) FROM payment_events').fetchone()[0],1)
 def test_underpayment_rejected(self):
  with self.assertRaises(ValueError):reconcile_sslcommerz(self.c,'TX1','VAL1',self.payload(amount='119.99'))
  self.assertEqual(self.c.execute('SELECT status FROM orders').fetchone()[0],'pending')
 def test_overpayment_rejected(self):
  with self.assertRaises(ValueError):reconcile_sslcommerz(self.c,'TX1','VAL1',self.payload(amount='120.01'))
 def test_nonfinite_rejected(self):
  with self.assertRaises(ValueError):reconcile_sslcommerz(self.c,'TX1','VAL1',self.payload(amount='NaN'))
 def test_transaction_mismatch(self):
  with self.assertRaises(ValueError):reconcile_sslcommerz(self.c,'TX1','VAL1',self.payload(tran_id='OTHER'))
 def test_replay_conflicting_validation(self):
  reconcile_sslcommerz(self.c,'TX1','VAL1',self.payload())
  with self.assertRaises(RuntimeError):reconcile_sslcommerz(self.c,'TX1','VAL2',self.payload())
 def test_invalid_currency(self):
  with self.assertRaises(ValueError):reconcile_sslcommerz(self.c,'TX1','VAL1',self.payload(currency='USD'))
if __name__=='__main__':unittest.main()
