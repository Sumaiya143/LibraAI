import unittest, sqlite3
from payout_review import review,install

class PayoutReviewTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:')
  self.c.execute('CREATE TABLE merchant_payouts(id INTEGER PRIMARY KEY,merchant_id INTEGER,amount TEXT,currency TEXT,status TEXT)')
  self.c.execute("INSERT INTO merchant_payouts VALUES(1,3,'1200.00','BDT','manual_review')")
 def tearDown(self):self.c.close()
 def test_approve_and_record(self):
  self.assertEqual(review(self.c,1,9,'approved')['status'],'approved')
  self.assertEqual(self.c.execute('SELECT count(*) FROM payout_review_events').fetchone()[0],1)
 def test_paid_requires_external_reference(self):
  review(self.c,1,9,'approved')
  with self.assertRaises(ValueError):review(self.c,1,9,'paid')
  self.assertEqual(review(self.c,1,9,'paid','BANK-123')['status'],'paid')
 def test_cannot_self_approve(self):
  with self.assertRaises(PermissionError):review(self.c,1,3,'approved')
 def test_cannot_skip_approval(self):
  with self.assertRaises(ValueError):review(self.c,1,9,'paid','BANK-123')
 def test_cannot_replay(self):
  review(self.c,1,9,'approved')
  with self.assertRaises(ValueError):review(self.c,1,9,'approved')
 def test_invalid_amount(self):
  self.c.execute("UPDATE merchant_payouts SET amount='NaN' WHERE id=1")
  with self.assertRaises(ValueError):review(self.c,1,9,'approved')
 def test_unknown_does_not_audit(self):
  with self.assertRaises(LookupError):review(self.c,999,9,'approved')
  self.assertEqual(self.c.execute('SELECT count(*) FROM payout_review_events').fetchone()[0],0)
 def test_reject_terminal(self):
  review(self.c,1,9,'rejected')
  with self.assertRaises(ValueError):review(self.c,1,9,'approved')
if __name__=='__main__':unittest.main()
