import csv
import tempfile
import unittest
from pathlib import Path
from refund_csv_export import safe_cell, export_refund_issues


class RefundCsvExportTests(unittest.TestCase):
    def test_formula_injection(self):
        for payload in ('=1+1', ' +SUM(A1)', '\t@cmd', '-5'):
            self.assertTrue(safe_cell(payload).startswith("'"))

    def test_privacy_and_headers(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'audit.csv'
            export_refund_issues({'issues': [{'refund_id': 5, 'order_id': 7,
                                              'issues': ['missing_order'], 'address': 'SECRET'}]}, path)
            with path.open(encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]['issue_codes'], 'missing_order')
            self.assertNotIn('SECRET', path.read_text(encoding='utf-8-sig'))

    def test_never_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'audit.csv'
            path.write_text('original')
            with self.assertRaises(FileExistsError):
                export_refund_issues({'issues': []}, path)
            self.assertEqual(path.read_text(), 'original')

    def test_requires_full_report(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                export_refund_issues({'issue_count': 2}, Path(temp) / 'audit.csv')
