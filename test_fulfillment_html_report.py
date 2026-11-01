import sqlite3
import tempfile
import unittest
from pathlib import Path
from mixed_fulfillment_audit import render_html_report, main
from test_mixed_fulfillment_audit import MixedFulfillmentAuditTests

class HtmlReportTests(unittest.TestCase):
    def test_escape_untrusted_status_and_issue(self):
        output = render_html_report({'order_id': 5, 'status': '<script>alert(1)</script>',
            'ready': False, 'issues': ['<img src=x onerror=alert(1)>']})
        self.assertNotIn('<script>', output)
        self.assertNotIn('<img', output)
        self.assertIn('&lt;script&gt;', output)
        self.assertIn('&lt;img', output)
    def test_batch_report(self):
        report = render_html_report({'orders': [
            {'order_id': 1, 'status': 'Processing', 'ready': True, 'issues': []},
            {'order_id': 2, 'status': 'Pending', 'ready': False, 'issues': ['missing']} ]})
        self.assertIn('READY', report)
        self.assertIn('REVIEW', report)
        self.assertIn('missing', report)
    def test_no_personal_details_rendered(self):
        report = render_html_report({'order_id': 3, 'status': 'Processing',
            'ready': True, 'issues': [], 'address': 'private address', 'user_id': 7})
        self.assertNotIn('private address', report)
        self.assertNotIn('user_id', report)
    def test_cli_creates_report_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td)/'db.sqlite'
            c = sqlite3.connect(db)
            c.executescript('''CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,status TEXT,address TEXT);
                CREATE TABLE order_items(order_id INTEGER,book_id INTEGER,format TEXT,quantity INTEGER);
                CREATE TABLE payment_attempts(order_id INTEGER,state TEXT);
                CREATE TABLE print_shipments(order_id INTEGER,state TEXT);
                CREATE TABLE licensed_documents(book_id INTEGER,access_policy TEXT);
                CREATE TABLE digital_entitlements(order_id INTEGER,user_id INTEGER,book_id INTEGER);
                INSERT INTO orders VALUES(1,7,'Processing','Dhaka');
                INSERT INTO order_items VALUES(1,11,'print',1);
                INSERT INTO payment_attempts VALUES(1,'paid');
                INSERT INTO print_shipments VALUES(1,'packing');''')
            c.commit(); c.close()
            report = Path(td)/'audit.html'
            self.assertEqual(main(['--db',str(db),'--order-id','1','--html-report',str(report)]),0)
            self.assertTrue(report.is_file())
            self.assertIn('LibraAI Fulfillment Audit', report.read_text())
            with self.assertRaises(SystemExit) as error:
                main(['--db',str(db),'--order-id','1','--html-report',str(report)])
            self.assertEqual(error.exception.code,1)
