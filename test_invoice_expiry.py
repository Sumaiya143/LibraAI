import sqlite3,unittest
from subscription_lifecycle import install,expire_invoices,create_invoice,cancel_invoice

class InvoiceExpiryTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
  self.c.execute("CREATE TABLE subscription_invoices(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,plan TEXT NOT NULL,amount TEXT NOT NULL,currency TEXT NOT NULL DEFAULT 'BDT',status TEXT NOT NULL DEFAULT 'unpaid',created TEXT DEFAULT CURRENT_TIMESTAMP)")
  install(self.c);self.c.commit()
 def tearDown(self):self.c.close()
 def test_new_invoice_has_expiry(self):
  r=create_invoice(self.c,1,'premium');self.assertTrue(r['expires_at']);self.assertEqual(r['status'],'unpaid')
 def test_expire_only_unpaid(self):
  self.c.execute("INSERT INTO subscription_invoices(user_id,plan,amount,status,expires_at) VALUES(1,'premium','999','unpaid','2020-01-01'),(1,'student','399','paid','2020-01-01')")
  self.assertEqual(expire_invoices(self.c,'2026-01-01'),1)
  self.assertEqual([r[0] for r in self.c.execute('SELECT status FROM subscription_invoices ORDER BY id')],['expired','paid'])
 def test_expired_invoice_can_be_replaced(self):
  self.c.execute("INSERT INTO subscription_invoices(user_id,plan,amount,status,expires_at) VALUES(1,'premium','999','unpaid','2020-01-01')");self.c.commit()
  r=create_invoice(self.c,1,'premium');self.assertFalse(r['reused']);self.assertEqual(r['invoice_id'],2)
 def test_expired_invoice_cannot_cancel(self):
  self.c.execute("INSERT INTO subscription_invoices(user_id,plan,amount,status,expires_at) VALUES(1,'premium','999','unpaid','2020-01-01')");self.c.commit()
  with self.assertRaises(ValueError):cancel_invoice(self.c,1,1)
 def test_legacy_migration_is_idempotent(self):
  install(self.c);install(self.c);self.assertIn('expires_at',[r[1] for r in self.c.execute('PRAGMA table_info(subscription_invoices)')])
if __name__=='__main__':unittest.main()
