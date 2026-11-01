import sqlite3, unittest
from payout_full_export import export_snapshot, ExportTooLarge
from payout_export import render_payout_csv

class FullPayoutExportTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
  self.c.executescript('''CREATE TABLE merchant_payouts(id INTEGER PRIMARY KEY,merchant_id INTEGER,amount TEXT,currency TEXT,status TEXT,created TEXT);CREATE TABLE payout_review_events(id INTEGER PRIMARY KEY,payout_id INTEGER,reviewer_id INTEGER,previous_status TEXT,new_status TEXT,reference TEXT,created TEXT);''')
 def tearDown(self):self.c.close()
 def test_all_rows_not_first_hundred(self):
  self.c.executemany('INSERT INTO merchant_payouts VALUES(?,1,"20","BDT","paid","today")',[(i,) for i in range(1,151)])
  self.assertEqual(len(export_snapshot(self.c)['payouts']),150)
 def test_no_silent_truncation(self):
  self.c.executemany('INSERT INTO merchant_payouts VALUES(?,1,"20","BDT","paid","today")',[(i,) for i in range(1,4)])
  with self.assertRaises(ExportTooLarge):export_snapshot(self.c,2)
 def test_events_complete_and_ordered(self):
  self.c.executemany('INSERT INTO payout_review_events VALUES(?,1,2,"pending","approved","ref","today")',[(i,) for i in (3,1,2)])
  self.assertEqual([r['id'] for r in export_snapshot(self.c)['review_events']],[1,2,3])
 def test_empty_csv_valid(self):
  self.assertIn(b'record_type',render_payout_csv(export_snapshot(self.c)))
 def test_invalid_limit(self):
  for limit in (0,-1,10001,True,'100'):
   with self.assertRaises(ValueError):export_snapshot(self.c,limit)
if __name__=='__main__':unittest.main()
