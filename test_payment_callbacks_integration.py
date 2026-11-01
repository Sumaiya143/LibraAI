"""Flask-route integration tests for real payment callback boundaries.

These tests exercise the registered HTTP endpoints with an isolated SQLite
ledger and mocked server-to-server gateway responses. They never contact a
payment provider or move money.
"""
import sqlite3
import unittest
from unittest.mock import patch

try:
    import app as libra_app
    import payment_routes
    from payment_engine import setup as payment_setup, create_attempt, mark_pending
    from digital_entitlements import setup as entitlement_setup
    FLASK_IMPORT_ERROR = None
except ModuleNotFoundError as exc:
    # The project CI installs requirements.txt; keep dependency-light source
    # audits runnable in environments that intentionally omit runtime packages.
    if exc.name not in {'flask', 'werkzeug'}:
        raise
    FLASK_IMPORT_ERROR = exc.name


@unittest.skipIf(FLASK_IMPORT_ERROR is not None, f'Flask runtime dependency unavailable: {FLASK_IMPORT_ERROR}')
class PaymentCallbackRouteIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.executescript('''
            CREATE TABLE orders(
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, total REAL NOT NULL,
                status TEXT NOT NULL, address TEXT, created TEXT
            );
            INSERT INTO orders VALUES(41, 7, 125.50, 'Awaiting payment', 'test', 'now');
            CREATE TABLE order_items(
                id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, book_id INTEGER NOT NULL,
                format TEXT NOT NULL, quantity INTEGER DEFAULT 1,
                unit_price_cents INTEGER DEFAULT 12550
            );
            CREATE TABLE licensed_documents(book_id INTEGER PRIMARY KEY, access_policy TEXT NOT NULL);
            INSERT INTO order_items VALUES(1,41,900,'eBook',1,12550);
            INSERT INTO licensed_documents VALUES(900,'licensed');
        ''')
        payment_setup(self.conn)
        entitlement_setup(self.conn)
        self.patcher = patch.object(libra_app, 'db', return_value=self.conn)
        self.patcher.start()
        self.client = libra_app.app.test_client()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def make_attempt(self, provider):
        attempt, _ = create_attempt(self.conn, 41, 7, provider, f'merchant-{provider}-41')
        provider_ref = f'provider-{provider}-41'
        mark_pending(self.conn, attempt['merchant_ref'], provider_ref)
        return attempt, provider_ref

    def state(self, merchant_ref):
        return self.conn.execute(
            'SELECT state FROM payment_attempts WHERE merchant_ref=?', (merchant_ref,)
        ).fetchone()['state']

    def test_bkash_callback_settles_only_after_execute_and_query_verification(self):
        attempt, payment_id = self.make_attempt('bkash')
        execute = {'statusCode': '0000', 'transactionStatus': 'Completed'}
        query = {
            'statusCode': '0000', 'transactionStatus': 'Completed',
            'paymentID': payment_id, 'merchantInvoiceNumber': attempt['merchant_ref'],
            'amount': '125.50', 'currency': 'BDT',
        }
        with patch.object(payment_routes, 'bkash_execute_and_query', return_value=(execute, query)):
            response = self.client.get('/payments/bkash/callback', query_string={
                'paymentID': payment_id, 'status': 'success'
            })
        self.assertEqual(response.status_code, 303)
        self.assertIn('/my/orders?payment=confirmed', response.headers['Location'])
        self.assertEqual(self.state(attempt['merchant_ref']), 'paid')
        self.assertEqual(self.conn.execute('SELECT status FROM orders WHERE id=41').fetchone()[0], 'Paid — fulfillment pending')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM digital_entitlements WHERE user_id=7 AND book_id=900').fetchone()[0], 1)

    def test_bkash_callback_amount_mismatch_does_not_settle_or_grant_access(self):
        attempt, payment_id = self.make_attempt('bkash')
        execute = {'statusCode': '0000'}
        query = {
            'statusCode': '0000', 'transactionStatus': 'Completed',
            'paymentID': payment_id, 'merchantInvoiceNumber': attempt['merchant_ref'],
            'amount': '124.50', 'currency': 'BDT',
        }
        with patch.object(payment_routes, 'bkash_execute_and_query', return_value=(execute, query)):
            response = self.client.get('/payments/bkash/callback', query_string={
                'paymentID': payment_id, 'status': 'success'
            })
        self.assertEqual(response.status_code, 303)
        self.assertIn('/my/orders?payment=unverified', response.headers['Location'])
        self.assertEqual(self.state(attempt['merchant_ref']), 'pending')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM digital_entitlements').fetchone()[0], 0)

    def test_sslcommerz_ipn_settles_only_after_server_validation(self):
        attempt, _ = self.make_attempt('sslcommerz')
        verified = {
            'status': 'VALID', 'tran_id': attempt['merchant_ref'], 'val_id': 'validated-41',
            'amount': '125.50', 'currency': 'BDT', 'risk_level': '0',
        }
        with patch.object(payment_routes, 'ssl_verify', return_value=verified):
            response = self.client.post('/payments/sslcommerz/ipn', data={
                'tran_id': attempt['merchant_ref'], 'val_id': 'validated-41'
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), 'OK')
        self.assertEqual(self.state(attempt['merchant_ref']), 'paid')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM digital_entitlements').fetchone()[0], 1)

    def test_sslcommerz_ipn_amount_mismatch_does_not_settle(self):
        attempt, _ = self.make_attempt('sslcommerz')
        verified = {
            'status': 'VALID', 'tran_id': attempt['merchant_ref'], 'val_id': 'validated-41',
            'amount': '125.49', 'currency': 'BDT', 'risk_level': '0',
        }
        with patch.object(payment_routes, 'ssl_verify', return_value=verified):
            response = self.client.post('/payments/sslcommerz/ipn', data={
                'tran_id': attempt['merchant_ref'], 'val_id': 'validated-41'
            })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.state(attempt['merchant_ref']), 'pending')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM digital_entitlements').fetchone()[0], 0)

    def test_browser_return_never_settles_sslcommerz_payment(self):
        attempt, _ = self.make_attempt('sslcommerz')
        response = self.client.get('/payments/sslcommerz/return', query_string={
            'status': 'VALID', 'tran_id': attempt['merchant_ref'], 'val_id': 'fake'
        })
        self.assertEqual(response.status_code, 303)
        self.assertIn('/my/orders?payment=processing', response.headers['Location'])
        self.assertEqual(self.state(attempt['merchant_ref']), 'pending')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM digital_entitlements').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
