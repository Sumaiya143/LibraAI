import csv
import io
import unittest
from payout_export import safe_cell,render_payout_csv

class PayoutExportTests(unittest.TestCase):
 def test_csv_contains_both_types(self):
  raw=render_payout_csv({'payouts':[{'id':1,'amount':'100','status':'approved'}], 'review_events':[{'id':2,'payout_id':1,'new_status':'approved'}]})
  rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
  self.assertEqual([r['record_type'] for r in rows],['payout','review_event'])
  self.assertEqual(rows[1]['status'],'approved')
 def test_formula_injection_prevention(self):
  for value in ('=SUM(1,1)','+1','-2','@cmd','  =1','\t+1'):
   with self.subTest(value=value):self.assertEqual(safe_cell(value),"'"+value)
 def test_null_and_utf8(self):
  self.assertEqual(safe_cell(None),'')
  raw=render_payout_csv({'payouts':[{'currency':'৳','amount':None}], 'review_events':[]})
  self.assertIn('৳',raw.decode('utf-8-sig'))
 def test_csv_escapes_commas_and_newlines(self):
  raw=render_payout_csv({'payouts':[{'status':'review, pending\nnext'}], 'review_events':[]})
  rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
  self.assertEqual(rows[0]['status'],'review, pending\nnext')
 def test_export_route_requires_admin(self):
  import inspect,commerce_server
  source=inspect.getsource(commerce_server.Commerce.do_GET)
  self.assertIn("p.path=='/api/admin/commerce/payouts/export.csv'",source)
  self.assertIn("u['role']!='admin'",source)
if __name__=='__main__':unittest.main()
