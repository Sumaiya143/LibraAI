import sqlite3,unittest
from payment_engine import setup,create_attempt,mark_pending,settle_verified,PaymentError,abandon_unlaunched_attempt

class PaymentTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
  self.c.executescript("CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,total REAL,status TEXT); INSERT INTO orders VALUES(1,7,125.50,'Awaiting payment — sandbox only');")
  self.c.executescript("CREATE TABLE order_items(order_id INTEGER,book_id INTEGER,format TEXT); CREATE TABLE licensed_documents(book_id INTEGER,access_policy TEXT);")
  from digital_entitlements import setup as setup_entitlements
  setup_entitlements(self.c)
  setup(self.c)
 def tearDown(self): self.c.close()
 def attempt(self,provider='bkash'):
  return create_attempt(self.c,1,7,provider,'ref1')[0]
 def test_attempt_amount(self): self.assertEqual(self.attempt()['amount_cents'],12550)
 def test_duplicate_attempt(self):
  self.attempt();a,new=create_attempt(self.c,1,7,'bkash','ref2');self.assertFalse(new);self.assertEqual(a['merchant_ref'],'ref1')
 def test_cross_gateway_attempt_rejected(self):
  self.attempt('bkash')
  with self.assertRaisesRegex(PaymentError,'another gateway'):
   create_attempt(self.c,1,7,'sslcommerz','ref2')
  self.assertEqual(self.c.execute('SELECT COUNT(*) FROM payment_attempts').fetchone()[0],1)
 def test_switch_gateway_only_before_launch(self):
  self.attempt('bkash')
  self.assertTrue(abandon_unlaunched_attempt(self.c,1,7,'ref1'))
  next_attempt,created=create_attempt(self.c,1,7,'sslcommerz','ref2')
  self.assertTrue(created);self.assertEqual(next_attempt['provider'],'sslcommerz')
  self.assertEqual(self.c.execute("SELECT state FROM payment_attempts WHERE merchant_ref='ref1'").fetchone()[0],'abandoned')
 def test_cannot_abandon_launched_session(self):
  self.attempt();mark_pending(self.c,'ref1','gateway123','https://example.com')
  with self.assertRaisesRegex(PaymentError,'reconciliation required'):
   abandon_unlaunched_attempt(self.c,1,7,'ref1')
  self.assertEqual(self.c.execute('SELECT state FROM payment_attempts').fetchone()[0],'pending')
 def test_cannot_abandon_other_users_attempt(self):
  self.attempt()
  with self.assertRaises(PaymentError):abandon_unlaunched_attempt(self.c,1,8,'ref1')
 def test_cannot_abandon_paid_attempt(self):
  self.attempt();mark_pending(self.c,'ref1','payment123')
  settle_verified(self.c,'ref1','bkash','payment123',12550,'BDT',True,'Completed')
  with self.assertRaises(PaymentError):abandon_unlaunched_attempt(self.c,1,7,'ref1')
 def test_pending_retry_keeps_original_gateway_url(self):
  self.attempt();mark_pending(self.c,'ref1','session123','https://gateway.example/pay')
  mark_pending(self.c,'ref1','session123')
  a=self.c.execute('SELECT gateway_url,provider_ref FROM payment_attempts').fetchone()
  self.assertEqual(a['gateway_url'],'https://gateway.example/pay')
  self.assertEqual(a['provider_ref'],'session123')
 def test_pending_retry_cannot_replace_gateway_url(self):
  self.attempt();mark_pending(self.c,'ref1','session123','https://gateway.example/pay')
  with self.assertRaisesRegex(PaymentError,'URL mismatch'):
   mark_pending(self.c,'ref1','session123','https://other.example/pay')
  self.assertEqual(self.c.execute('SELECT gateway_url FROM payment_attempts').fetchone()[0],'https://gateway.example/pay')
 def test_pending_requires_gateway_reference(self):
  self.attempt()
  with self.assertRaisesRegex(PaymentError,'Missing gateway session reference'):
   mark_pending(self.c,'ref1',None)
  self.assertEqual(self.c.execute('SELECT state FROM payment_attempts').fetchone()[0],'created')
 def test_cancelled_order_cannot_launch_gateway_session(self):
  self.attempt();self.c.execute("UPDATE orders SET status='Cancelled' WHERE id=1");self.c.commit()
  with self.assertRaisesRegex(PaymentError,'no longer payable'):
   mark_pending(self.c,'ref1','gateway123')
  self.assertEqual(self.c.execute('SELECT state FROM payment_attempts').fetchone()[0],'created')
 def test_changed_total_cannot_launch_gateway_session(self):
  self.attempt();self.c.execute('UPDATE orders SET total=130 WHERE id=1');self.c.commit()
  with self.assertRaisesRegex(PaymentError,'total changed'):
   mark_pending(self.c,'ref1','gateway123')
  self.assertEqual(self.c.execute('SELECT state FROM payment_attempts').fetchone()[0],'created')
 def test_deleted_order_cannot_launch_gateway_session(self):
  self.attempt();self.c.execute('DELETE FROM orders WHERE id=1');self.c.commit()
  with self.assertRaisesRegex(PaymentError,'no longer payable'):
   mark_pending(self.c,'ref1','gateway123')
 def test_wrong_owner(self):
  with self.assertRaises(PaymentError):create_attempt(self.c,1,8,'bkash','r')
 def test_unsupported_provider(self):
  with self.assertRaises(PaymentError):create_attempt(self.c,1,7,'other','r')
 def test_verified_amount_rejects_boolean(self):
  self.attempt()
  with self.assertRaisesRegex(PaymentError,'Invalid verified amount'):
   settle_verified(self.c,'ref1','bkash','payment123',True,'BDT',True,'Completed')
 def test_verified_amount_rejects_float(self):
  self.attempt()
  with self.assertRaisesRegex(PaymentError,'Invalid verified amount'):
   settle_verified(self.c,'ref1','bkash','payment123',12550.0,'BDT',True,'Completed')
 def test_verified_reference_rejects_non_string(self):
  self.attempt()
  with self.assertRaisesRegex(PaymentError,'Invalid provider transaction reference'):
   settle_verified(self.c,'ref1','bkash',123,12550,'BDT',True,'Completed')
 def test_gateway_reference_rejects_oversized(self):
  self.attempt()
  with self.assertRaisesRegex(PaymentError,'Invalid gateway session reference'):
   mark_pending(self.c,'ref1','x'*256)
 def test_truthy_string_cannot_settle(self):
  self.attempt()
  with self.assertRaisesRegex(PaymentError,'not independently verified'):
   settle_verified(self.c,'ref1','bkash','payment123',12550,'BDT','false','Completed')
  self.assertEqual(self.c.execute("SELECT COUNT(*) FROM payment_events").fetchone()[0],0)
 def test_truthy_integer_cannot_settle(self):
  self.attempt()
  with self.assertRaises(PaymentError):
   settle_verified(self.c,'ref1','bkash','payment123',12550,'BDT',1,'Completed')
 def test_invalid_merchant_references_rejected(self):
  for ref in ('', ' ', ' leading', 'trailing ', 'x'*256, None, 42):
   with self.subTest(ref=ref):
    with self.assertRaisesRegex(PaymentError,'Invalid merchant reference'):
     create_attempt(self.c,1,7,'bkash',ref)
  self.assertEqual(self.c.execute('SELECT COUNT(*) FROM payment_attempts').fetchone()[0],0)
 def test_browser_claim_cannot_settle(self):
  self.attempt()
  with self.assertRaises(PaymentError):settle_verified(self.c,'ref1','bkash','payment123',12550,'BDT',False,'Completed')
 def test_amount_mismatch(self):
  self.attempt()
  with self.assertRaises(PaymentError):settle_verified(self.c,'ref1','bkash','payment123',12549,'BDT',True,'Completed')
 def test_currency_mismatch(self):
  self.attempt()
  with self.assertRaises(PaymentError):settle_verified(self.c,'ref1','bkash','payment123',12550,'USD',True,'Completed')
 def test_verified_settlement_idempotent(self):
  self.attempt();mark_pending(self.c,'ref1','payment123','https://example.com')
  self.assertTrue(settle_verified(self.c,'ref1','bkash','payment123',12550,'BDT',True,'Completed'))
  self.assertFalse(settle_verified(self.c,'ref1','bkash','payment123',12550,'BDT',True,'Completed'))
  self.assertEqual(self.c.execute('SELECT status FROM orders WHERE id=1').fetchone()[0],'Paid — fulfillment pending')
  self.assertEqual(self.c.execute('SELECT count(*) FROM payment_events').fetchone()[0],1)
 def test_paid_replay_with_different_reference_rejected(self):
  self.attempt();mark_pending(self.c,'ref1','payment123')
  self.assertTrue(settle_verified(self.c,'ref1','bkash','payment123',12550,'BDT',True,'Completed'))
  with self.assertRaisesRegex(PaymentError,'Conflicting transaction reference'):
   settle_verified(self.c,'ref1','bkash','payment456',12550,'BDT',True,'Completed')
  self.assertEqual(self.c.execute('SELECT count(*) FROM payment_events').fetchone()[0],1)
 def test_ssl_paid_replay_with_different_reference_rejected(self):
  self.attempt('sslcommerz');mark_pending(self.c,'ref1','session123')
  self.assertTrue(settle_verified(self.c,'ref1','sslcommerz','transaction123',12550,'BDT',True,'VALID'))
  with self.assertRaisesRegex(PaymentError,'Conflicting transaction reference'):
   settle_verified(self.c,'ref1','sslcommerz','transaction456',12550,'BDT',True,'VALID')
  self.assertFalse(settle_verified(self.c,'ref1','sslcommerz','transaction123',12550,'BDT',True,'VALID'))
 def test_cancelled_order_cannot_settle(self):
  self.attempt();self.c.execute("UPDATE orders SET status='Cancelled — sandbox' WHERE id=1");self.c.commit()
  with self.assertRaises(PaymentError):settle_verified(self.c,'ref1','bkash','payment123',12550,'BDT',True,'Completed')
 def test_order_price_change_blocks_settlement(self):
  self.attempt();self.c.execute('UPDATE orders SET total=999 WHERE id=1');self.c.commit()
  with self.assertRaisesRegex(PaymentError,'Order total changed'):
   settle_verified(self.c,'ref1','bkash','payment123',12550,'BDT',True,'Completed')
  self.assertEqual(self.c.execute('SELECT state FROM payment_attempts').fetchone()[0],'created')
  self.assertEqual(self.c.execute('SELECT status FROM orders').fetchone()[0],'Awaiting payment — sandbox only')
 def test_order_price_change_blocks_reused_attempt(self):
  self.attempt();self.c.execute('UPDATE orders SET total=130 WHERE id=1');self.c.commit()
  with self.assertRaisesRegex(PaymentError,'Order total changed'):
   create_attempt(self.c,1,7,'bkash','ref2')
  self.assertEqual(self.c.execute('SELECT COUNT(*) FROM payment_attempts').fetchone()[0],1)
 def test_reference_mismatch(self):
  self.attempt();mark_pending(self.c,'ref1','payment123')
  with self.assertRaises(PaymentError):settle_verified(self.c,'ref1','bkash','other',12550,'BDT',True,'Completed')
 def test_ssl_session_to_transaction(self):
  self.attempt('sslcommerz');mark_pending(self.c,'ref1','session123')
  self.assertTrue(settle_verified(self.c,'ref1','sslcommerz','bank_transaction123',12550,'BDT',True,'VALID'))

if __name__=='__main__':unittest.main()
