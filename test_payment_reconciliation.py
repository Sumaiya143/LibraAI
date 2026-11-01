import os,sqlite3,unittest
from unittest.mock import patch
from payment_engine import setup,create_attempt,mark_pending,pending_for_reconciliation,PaymentError
from payment_reconciliation import reconcile_one
class ReconciliationTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
  self.c.executescript("CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,total REAL,status TEXT); INSERT INTO orders VALUES(1,7,125.50,'Awaiting payment');")
  setup(self.c)
  self.c.executescript("CREATE TABLE order_items(order_id INTEGER,book_id INTEGER,format TEXT); CREATE TABLE licensed_documents(book_id INTEGER,access_policy TEXT);")
 def tearDown(self):self.c.close()
 def make(self,provider):
  create_attempt(self.c,1,7,provider,'ref1');mark_pending(self.c,'ref1','pay123')
  return pending_for_reconciliation(self.c)[0]
 def test_pending_list(self):
  self.make('bkash');self.assertEqual(len(pending_for_reconciliation(self.c)),1)
 def test_invalid_limit(self):
  with self.assertRaises(PaymentError):pending_for_reconciliation(self.c,0)
 def test_bkash_dry_run_does_not_pay(self):
  a=self.make('bkash');r={'statusCode':'0000','transactionStatus':'Completed','paymentID':'pay123','merchantInvoiceNumber':'ref1','amount':'125.50','currency':'BDT'}
  self.assertEqual(reconcile_one(self.c,a,query_bkash=lambda _:r),'verified_dry_run')
  self.assertEqual(self.c.execute('SELECT status FROM orders').fetchone()[0],'Awaiting payment')
 def test_bkash_settlement(self):
  a=self.make('bkash');r={'statusCode':'0000','transactionStatus':'Completed','paymentID':'pay123','merchantInvoiceNumber':'ref1','amount':'125.50','currency':'BDT'}
  self.assertEqual(reconcile_one(self.c,a,query_bkash=lambda _:r,apply=True),'settled')
  self.assertEqual(self.c.execute('SELECT status FROM orders').fetchone()[0],'Paid — fulfillment pending')
 def test_wrong_invoice_rejected(self):
  a=self.make('bkash');r={'statusCode':'0000','transactionStatus':'Completed','paymentID':'pay123','merchantInvoiceNumber':'evil','amount':'125.50','currency':'BDT'}
  with self.assertRaises(PaymentError):reconcile_one(self.c,a,query_bkash=lambda _:r,apply=True)
 def test_wrong_amount_rejected(self):
  a=self.make('bkash');r={'statusCode':'0000','transactionStatus':'Completed','paymentID':'pay123','merchantInvoiceNumber':'ref1','amount':'1.00','currency':'BDT'}
  with self.assertRaises(PaymentError):reconcile_one(self.c,a,query_bkash=lambda _:r,apply=True)
 def test_bkash_malformed_provider_response_rejected(self):
  a=self.make('bkash')
  for response in (None, [], 'Completed', True):
   with self.subTest(response=response):
    with self.assertRaisesRegex(PaymentError,'Malformed bKash'):
     reconcile_one(self.c,a,query_bkash=lambda _:response,apply=True)
  self.assertEqual(self.c.execute('SELECT status FROM orders').fetchone()[0],'Awaiting payment')
 def test_ssl_malformed_provider_response_rejected(self):
  a=self.make('sslcommerz')
  with patch.dict(os.environ,{'SSLCOMMERZ_STORE_ID':'store','SSLCOMMERZ_STORE_PASSWORD':'password'}):
   for response in (None, [], 'VALID', True):
    with self.subTest(response=response):
     with self.assertRaisesRegex(PaymentError,'Malformed SSLCommerz'):
      reconcile_one(self.c,a,verify_ssl=lambda _:response,apply=True)
  self.assertEqual(self.c.execute('SELECT status FROM orders').fetchone()[0],'Awaiting payment')
 def test_ssl_risk_rejected(self):
  a=self.make('sslcommerz');r={'status':'VALID','tran_id':'ref1','amount':'125.50','currency':'BDT','bank_tran_id':'bank1','risk_level':'1'}
  with patch.dict(os.environ,{'SSLCOMMERZ_STORE_ID':'store','SSLCOMMERZ_STORE_PASSWORD':'password'}):
   with self.assertRaises(PaymentError):reconcile_one(self.c,a,verify_ssl=lambda _:r,apply=True)
 def test_ssl_dry_run(self):
  a=self.make('sslcommerz');r={'status':'VALID','tran_id':'ref1','amount':'125.50','currency':'BDT','bank_tran_id':'bank1','risk_level':'0'}
  with patch.dict(os.environ,{'SSLCOMMERZ_STORE_ID':'store','SSLCOMMERZ_STORE_PASSWORD':'password'}):
   self.assertEqual(reconcile_one(self.c,a,verify_ssl=lambda _:r),'verified_dry_run')
if __name__=='__main__':unittest.main()
