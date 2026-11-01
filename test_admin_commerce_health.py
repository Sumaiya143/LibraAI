"""Security regression tests for the admin-only commerce diagnostics endpoint."""
import unittest
from unittest.mock import patch
from commerce_server import Commerce


class AdminHealthEndpointTests(unittest.TestCase):
    def call(self, user):
        handler = object.__new__(Commerce)
        handler.path = '/api/admin/commerce/health'
        handler.user = lambda: user
        sent = []
        handler.send = lambda status, payload: sent.append((status, payload))
        with patch('commerce_server.db') as db_mock, patch('commerce_server.assess_commerce_health') as assess:
            assess.return_value = {'status': 'no_detected_anomalies', 'findings': []}
            handler.do_GET()
            return sent, db_mock, assess

    def test_anonymous_is_denied_without_database_access(self):
        sent, db_mock, assess = self.call(None)
        self.assertEqual(sent[0][0], 401)
        db_mock.assert_not_called()
        assess.assert_not_called()

    def test_customer_is_denied_without_database_access(self):
        sent, db_mock, assess = self.call({'id': 1, 'role': 'customer'})
        self.assertEqual(sent[0][0], 403)
        db_mock.assert_not_called()
        assess.assert_not_called()

    def test_merchant_is_denied_without_database_access(self):
        sent, db_mock, assess = self.call({'id': 2, 'role': 'merchant'})
        self.assertEqual(sent[0][0], 403)
        db_mock.assert_not_called()
        assess.assert_not_called()

    def test_admin_receives_health_report(self):
        sent, db_mock, assess = self.call({'id': 3, 'role': 'admin'})
        self.assertEqual(sent, [(200, {'status': 'no_detected_anomalies', 'findings': []})])
        db_mock.assert_called_once()
        assess.assert_called_once()


if __name__ == '__main__':
    unittest.main()
