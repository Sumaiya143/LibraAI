import csv
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from finance_export import report, csv_text, safe_cell, export_database

class FinanceExportTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE orders (id INTEGER PRIMARY KEY, status TEXT, total REAL)')
        self.db.execute('CREATE TABLE payment_attempts (id INTEGER PRIMARY KEY, order_id INTEGER, provider TEXT, state TEXT, amount_cents INTEGER)')
        self.db.execute('CREATE TABLE refund_requests (id INTEGER PRIMARY KEY, attempt_id INTEGER, state TEXT, amount_cents INTEGER)')
        self.db.execute('INSERT INTO orders VALUES (1,?,?)',('Paid — fulfillment pending',125.50))
        self.db.execute('INSERT INTO payment_attempts VALUES (1,1,?,?,?)',('bkash','paid',12550))
        self.db.execute('INSERT INTO refund_requests VALUES (1,1,?,?)',('refunded',2500))
        self.db.commit()
    def tearDown(self): self.db.close()
    def test_paid_and_refunded(self):
        r=report(self.db)[0]
        self.assertEqual(r['paid_bdt'],'125.50')
        self.assertEqual(r['verified_refunds_bdt'],'25.00')
        self.assertEqual(r['remaining_paid_bdt'],'100.50')
    def test_pending_refund_not_counted_as_refunded(self):
        self.db.execute('INSERT INTO refund_requests VALUES (2,1,?,?)',('approved',1500))
        r=report(self.db)[0]
        self.assertEqual(r['remaining_paid_bdt'],'100.50')
        self.assertEqual(r['refunds_awaiting_gateway_bdt'],'15.00')
    def test_unpaid_order(self):
        self.db.execute('INSERT INTO orders VALUES (2,?,?)',('Awaiting payment',80))
        self.assertEqual(report(self.db)[1]['paid_bdt'],'0.00')
    def test_detect_amount_mismatch(self):
        self.db.execute('UPDATE payment_attempts SET amount_cents=12400')
        self.assertIn('AMOUNT_MISMATCH',report(self.db)[0]['review_flag'])
    def test_detect_over_refund(self):
        self.db.execute('UPDATE refund_requests SET amount_cents=15000')
        self.assertIn('OVER_REFUND',report(self.db)[0]['review_flag'])
    def test_csv_injection(self):
        for v in ('=1+1','+cmd','-cmd','@sum','  =HYPERLINK(1)'):
            self.assertTrue(safe_cell(v).startswith("'"))
    def test_csv_roundtrip(self):
        data=csv_text(report(self.db))
        row=list(csv.DictReader(io.StringIO(data)))[0]
        self.assertEqual(row['payment_provider'],'bkash')
    def test_read_only_file_export(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.sqlite'; out=Path(d)/'report.csv'
            disk=sqlite3.connect(p)
            self.db.backup(disk); disk.close()
            result=export_database(p,out)
            self.assertEqual(result['rows'],1)
            self.assertIn('125.50',out.read_text(encoding='utf-8-sig'))

    def test_export_does_not_overwrite_existing_report(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.sqlite'; out=Path(d)/'report.csv'
            disk=sqlite3.connect(p); self.db.backup(disk); disk.close()
            out.write_text('preserve this report', encoding='utf-8')
            with self.assertRaises(FileExistsError): export_database(p,out)
            self.assertEqual(out.read_text(encoding='utf-8'), 'preserve this report')

    def test_export_rejects_symlink_destination(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.sqlite'; target=Path(d)/'important.txt'; out=Path(d)/'report.csv'
            disk=sqlite3.connect(p); self.db.backup(disk); disk.close()
            target.write_text('do not overwrite', encoding='utf-8')
            try:
                out.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest('Symlinks unavailable in this environment')
            with self.assertRaises(ValueError): export_database(p,out)
            self.assertEqual(target.read_text(encoding='utf-8'), 'do not overwrite')

    def test_export_requires_csv_extension(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.sqlite'; out=Path(d)/'report.txt'
            disk=sqlite3.connect(p); self.db.backup(disk); disk.close()
            with self.assertRaises(ValueError): export_database(p,out)
            self.assertFalse(out.exists())

    def test_cannot_overwrite_database(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.sqlite'
            disk=sqlite3.connect(p); self.db.backup(disk); disk.close()
            with self.assertRaises(ValueError): export_database(p,p)

if __name__=='__main__': unittest.main()
