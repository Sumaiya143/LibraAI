import sqlite3,unittest
from payment_engine import setup as payment_setup,create_attempt,mark_pending,settle_verified
from refund_engine import setup,request_refund,review_refund,confirm_provider_refund,RefundError

class RefundTests(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
  self.db.execute("CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,total REAL,status TEXT)")
  self.db.execute("INSERT INTO orders VALUES(1,7,125.50,'Awaiting payment')")
  self.db.executescript("CREATE TABLE order_items(order_id INTEGER,book_id INTEGER,format TEXT); CREATE TABLE licensed_documents(book_id INTEGER,access_policy TEXT);")
  from digital_entitlements import setup as entitlement_setup
  entitlement_setup(self.db)
  payment_setup(self.db);setup(self.db)
  create_attempt(self.db,1,7,'bkash','r1');mark_pending(self.db,'r1','bkash-id')
  settle_verified(self.db,'r1','bkash','bkash-id',12550,'BDT',True,'Completed')
 def tearDown(self):self.db.close()
 def request(self,amount=5000):return request_refund(self.db,1,7,amount,'Customer requested refund')
 def test_requires_paid(self):
  self.db.execute("UPDATE payment_attempts SET state='pending'");self.db.commit()
  with self.assertRaises(RefundError):self.request()
 def test_owner(self):
  with self.assertRaises(RefundError):request_refund(self.db,1,8,100,'Valid reason')
 def test_amount_limit_and_reservations(self):
  self.request(10000)
  with self.assertRaises(RefundError):self.request(3000)
 def test_rejected_refund_releases_balance(self):
  rid=self.request(10000);review_refund(self.db,rid,99,False,admin=True)
  self.assertIsInstance(self.request(12550),int)
 def test_admin_only_review(self):
  rid=self.request()
  with self.assertRaises(RefundError):review_refund(self.db,rid,7,True)
 def test_browser_cannot_confirm(self):
  rid=self.request();review_refund(self.db,rid,99,True,admin=True)
  with self.assertRaises(RefundError):confirm_provider_refund(self.db,rid,'gateway-ref',verified=False)
 def test_unapproved_cannot_confirm(self):
  rid=self.request()
  with self.assertRaises(RefundError):confirm_provider_refund(self.db,rid,'gateway-ref',verified=True)
 def test_verified_idempotency(self):
  rid=self.request();review_refund(self.db,rid,99,True,admin=True)
  self.assertTrue(confirm_provider_refund(self.db,rid,'gateway-ref',verified=True))
  self.assertFalse(confirm_provider_refund(self.db,rid,'gateway-ref',verified=True))
  with self.assertRaises(RefundError):confirm_provider_refund(self.db,rid,'different-ref',verified=True)
 def test_provider_reference_unique(self):
  r1=self.request(2000);r2=self.request(3000)
  review_refund(self.db,r1,99,True,admin=True);review_refund(self.db,r2,99,True,admin=True)
  confirm_provider_refund(self.db,r1,'gateway-ref',verified=True)
  with self.assertRaises(sqlite3.IntegrityError):confirm_provider_refund(self.db,r2,'gateway-ref',verified=True)
 def test_string_verified_is_rejected(self):
  rid=self.request();review_refund(self.db,rid,99,True,admin=True)
  for value in ('false','true',1,[],None):
   with self.subTest(value=value),self.assertRaises(RefundError):
    confirm_provider_refund(self.db,rid,'gateway-ref',verified=value)
  self.assertEqual(self.db.execute('SELECT state FROM refund_requests WHERE id=?',(rid,)).fetchone()[0],'approved')
 def test_provider_ref_rejects_whitespace_and_control_characters(self):
  rid=self.request();review_refund(self.db,rid,99,True,admin=True)
  for ref in (' ref','ref ', 'ref\nabc','ref/abc','a'*161):
   with self.subTest(ref=ref),self.assertRaises(RefundError):
    confirm_provider_refund(self.db,rid,ref,verified=True)
 def test_duplicate_paid_attempts_block_automatic_refund_allocation(self):
  self.db.execute("DROP INDEX one_paid_payment_per_order")
  self.db.execute("INSERT INTO payment_attempts(order_id,provider,merchant_ref,amount_cents,currency,state,created,updated) SELECT order_id,provider,'other-ref',amount_cents,currency,'paid',created,updated FROM payment_attempts LIMIT 1")
  self.db.commit()
  with self.assertRaisesRegex(RefundError,'Multiple paid attempts'):
   self.request()
 def test_boolean_order_id_is_rejected(self):
  with self.assertRaises(RefundError): request_refund(self.db,True,7,100,'Valid reason')
 def test_invalid_reason(self):
  with self.assertRaises(RefundError):request_refund(self.db,1,7,100,'no')

if __name__=='__main__':unittest.main()
