import csv
import tempfile
import unittest
from pathlib import Path
from payment_csv_export import export_payment_issues
from payment_batch_audit import scan
from test_payment_batch_audit import BatchAuditTests


class PaymentCsvExportTests(BatchAuditTests):
    def test_csv_from_real_scan(self):
        report = scan(self.db, page_size=1)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'payment.csv'
            count = export_payment_issues(report, target)
            with target.open(encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(count, len(rows))
            self.assertGreater(count, 0)
            self.assertEqual(set(rows[0]), {'attempt_id', 'order_id', 'issue'})
            self.assertEqual(self.db.execute('SELECT count(*) FROM payment_attempts').fetchone()[0], 4)

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'report.csv'
            target.write_text('original')
            with self.assertRaises(FileExistsError):
                export_payment_issues({'anomalies': []}, target)
            self.assertEqual(target.read_text(), 'original')

    def test_rejects_spreadsheet_injection(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'report.csv'
            for payload in ({'attempt_id': '=1+1', 'order_id': 1, 'issues': ['missing_order']},
                            {'attempt_id': 1, 'order_id': 1, 'issues': ['=HYPERLINK']},
                            {'attempt_id': 1, 'order_id': 1, 'issues': ['issue\nline']}):
                with self.assertRaises(ValueError):
                    export_payment_issues({'anomalies': [payload]}, target)
                self.assertFalse(target.exists())

    def test_rejects_summary_and_wrong_extension(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                export_payment_issues({'checked': 4}, Path(folder) / 'a.csv')
            with self.assertRaises(ValueError):
                export_payment_issues({'anomalies': []}, Path(folder) / 'a.txt')


if __name__ == '__main__':
    unittest.main()
