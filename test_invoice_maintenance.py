import sqlite3
import tempfile
import unittest
from invoice_maintenance import expire_due
from subscription_lifecycle import install, create_invoice


class InvoiceMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(self.tmp.name + '/invoice.db')
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE subscription_invoices(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,plan TEXT NOT NULL,amount TEXT NOT NULL,currency TEXT NOT NULL DEFAULT 'BDT',status TEXT NOT NULL DEFAULT 'unpaid',created TEXT DEFAULT CURRENT_TIMESTAMP)")
        install(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_expire_due_and_idempotence(self):
        invoice = create_invoice(self.conn, 1, 'premium')['invoice_id']
        self.assertEqual(expire_due(self.conn, '2099-01-01 00:00:00'), 1)
        self.assertEqual(expire_due(self.conn, '2099-01-01 00:00:00'), 0)
        self.assertEqual(self.conn.execute('SELECT status FROM subscription_invoices WHERE id=?', (invoice,)).fetchone()[0], 'expired')

    def test_paid_and_cancelled_untouched(self):
        first = create_invoice(self.conn, 1, 'premium')['invoice_id']
        second = create_invoice(self.conn, 2, 'student')['invoice_id']
        self.conn.execute("UPDATE subscription_invoices SET status='paid' WHERE id=?", (first,))
        self.conn.execute("UPDATE subscription_invoices SET status='cancelled' WHERE id=?", (second,))
        self.conn.commit()
        self.assertEqual(expire_due(self.conn, '2099-01-01 00:00:00'), 0)
        self.assertEqual([x[0] for x in self.conn.execute('SELECT status FROM subscription_invoices ORDER BY id')], ['paid', 'cancelled'])

    def test_not_yet_expired(self):
        create_invoice(self.conn, 1, 'premium')
        self.assertEqual(expire_due(self.conn, '2000-01-01 00:00:00'), 0)

    def test_expired_allows_new_invoice(self):
        first = create_invoice(self.conn, 1, 'premium')['invoice_id']
        expire_due(self.conn, '2099-01-01 00:00:00')
        second = create_invoice(self.conn, 1, 'premium')['invoice_id']
        self.assertNotEqual(first, second)


if __name__ == '__main__':
    unittest.main()
