import csv
import io
import unittest
from mixed_fulfillment_audit import write_csv_report

class FulfillmentCsvReportTests(unittest.TestCase):
    def test_csv_safe_export(self):
        result = {'orders': [
            {'order_id': 7, 'ready': False, 'status': '=1+2', 'issues': ['@malicious']},
            {'order_id': 8, 'ready': True, 'status': 'Processing', 'issues': []}]}
        out = io.StringIO()
        write_csv_report(result, out)
        rows = list(csv.reader(io.StringIO(out.getvalue())))
        self.assertEqual(rows[0], ['order_id','result','status','issue_codes'])
        self.assertEqual(rows[1][2], "'=1+2")
        self.assertEqual(rows[1][3], "'@malicious")
        self.assertEqual(rows[2], ['8','READY','Processing',''])
        self.assertNotIn('address', out.getvalue())

    def test_single_order(self):
        out = io.StringIO()
        write_csv_report({'order_id': 1, 'ready': False, 'status': 'Pending', 'issues': ['missing']}, out)
        self.assertEqual(len(list(csv.reader(io.StringIO(out.getvalue())))), 2)

if __name__ == '__main__': unittest.main()
