import sqlite3,tempfile,unittest
from subscription_lifecycle import install,create_invoice,cancel_invoice
class LifecycleTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.c=sqlite3.connect(self.temp.name+'/test.sqlite3');self.c.row_factory=sqlite3.Row
  self.c.execute("CREATE TABLE subscription_invoices(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,plan TEXT NOT NULL,amount TEXT NOT NULL,currency TEXT NOT NULL DEFAULT 'BDT',status TEXT NOT NULL DEFAULT 'unpaid',created TEXT DEFAULT CURRENT_TIMESTAMP)")
  install(self.c)
 def tearDown(self):self.c.close();self.temp.cleanup()
 def test_create(self):
  r=create_invoice(self.c,1,'student');self.assertEqual(r['amount'],'399.00');self.assertFalse(r['reused'])
 def test_retry_idempotent(self):
  a=create_invoice(self.c,1,'premium');b=create_invoice(self.c,1,'premium');self.assertEqual(a['invoice_id'],b['invoice_id']);self.assertTrue(b['reused'])
 def test_other_user_separate(self):
  self.assertNotEqual(create_invoice(self.c,1,'premium')['invoice_id'],create_invoice(self.c,2,'premium')['invoice_id'])
 def test_cancel(self):
  a=create_invoice(self.c,1,'premium');self.assertEqual(cancel_invoice(self.c,1,a['invoice_id'])['status'],'cancelled');self.assertNotEqual(create_invoice(self.c,1,'premium')['invoice_id'],a['invoice_id'])
 def test_other_user_cannot_cancel(self):
  a=create_invoice(self.c,1,'premium');self.assertRaises(LookupError,cancel_invoice,self.c,2,a['invoice_id'])
 def test_cannot_cancel_twice(self):
  a=create_invoice(self.c,1,'premium');cancel_invoice(self.c,1,a['invoice_id']);self.assertRaises(ValueError,cancel_invoice,self.c,1,a['invoice_id'])
 def test_reject_invalid_plan(self):
  self.assertRaises(ValueError,create_invoice,self.c,1,'enterprise')
 def test_paid_invoice_not_cancellable(self):
  a=create_invoice(self.c,1,'premium');self.c.execute("UPDATE subscription_invoices SET status='paid' WHERE id=?",(a['invoice_id'],));self.c.commit();self.assertRaises(ValueError,cancel_invoice,self.c,1,a['invoice_id'])
if __name__=='__main__':unittest.main()
