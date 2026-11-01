import sqlite3
import unittest
from commerce_health import assess


class CommerceHealthTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.executescript('''
            CREATE TABLE subscription_invoices(status TEXT, expires_at TEXT);
            CREATE TABLE bkash_attempts(status TEXT, trx_id TEXT);
            CREATE TABLE orders(status TEXT);
            CREATE TABLE merchant_payouts(status TEXT);
        ''')

    def tearDown(self):
        self.conn.close()

    def test_empty_initialized_database(self):
        self.assertEqual(assess(self.conn)['status'], 'no_detected_anomalies')

    def test_overdue_invoice_warning(self):
        self.conn.execute("INSERT INTO subscription_invoices VALUES ('unpaid','2000-01-01')")
        result = assess(self.conn)
        self.assertEqual(result['status'], 'attention_required')
        self.assertIn('OVERDUE_INVOICES', [x['code'] for x in result['findings']])

    def test_duplicate_transaction_critical(self):
        self.conn.executemany('INSERT INTO bkash_attempts VALUES (?,?)', [('validated','same'),('validated','same')])
        result = assess(self.conn)
        self.assertIn('DUPLICATE_TRANSACTION_IDS', [x['code'] for x in result['findings']])

    def test_missing_tables_is_incomplete(self):
        self.conn.execute('DROP TABLE orders')
        self.assertEqual(assess(self.conn)['status'], 'incomplete')

    def test_missing_columns_is_incomplete(self):
        self.conn.execute('DROP TABLE bkash_attempts')
        self.conn.execute('CREATE TABLE bkash_attempts(status TEXT)')
        self.assertEqual(assess(self.conn)['status'], 'incomplete')

    def test_read_only(self):
        before = self.conn.total_changes
        assess(self.conn)
        self.assertEqual(before, self.conn.total_changes)
