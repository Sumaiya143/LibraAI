import csv
import io
import unittest
from refund_queue_csv import queue_page_csv, FIELDS

class QueueCsvTests(unittest.TestCase):
    def test_columns_are_allowlisted(self):
        report={'items':[dict(id=1,order_id=2,amount_cents=300,state='requested',created='a',updated='b',provider='bkash',reason='private',merchant_ref='secret',email='private@example.org')]}
        data=queue_page_csv(report)
        self.assertEqual(tuple(next(csv.reader(io.StringIO(data)))),FIELDS)
        self.assertNotIn('private',data)
        self.assertNotIn('secret',data)
    def test_spreadsheet_formula_injection(self):
        report={'items':[{'id':1,'provider':'=HYPERLINK("https://example.org")','created':'\t+SUM(1,2)','state':'@cmd'}]}
        data=queue_page_csv(report)
        row=list(csv.DictReader(io.StringIO(data)))[0]
        self.assertTrue(row['provider'].startswith("'="))
        self.assertTrue(row['created'].startswith("'\t"))
        self.assertTrue(row['state'].startswith("'@"))
    def test_empty_page_still_has_header(self):
        self.assertEqual(len(list(csv.reader(io.StringIO(queue_page_csv({'items':[]}))))),1)
    def test_quoted_csv_values(self):
        report={'items':[{'id':1,'provider':'a,b\n"c"'}]}
        self.assertEqual(list(csv.DictReader(io.StringIO(queue_page_csv(report))))[0]['provider'],'a,b\n"c"')

if __name__=='__main__': unittest.main()
