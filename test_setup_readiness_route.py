"""Flask-level access-control tests for the operator-only readiness endpoint."""
import unittest
from unittest.mock import patch

from app import app as flask_app


class SetupReadinessRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = flask_app.test_client()

    def test_anonymous_request_is_rejected_without_caching(self):
        with patch('app.current_user', return_value=None):
            response = self.client.get('/api/setup/readiness')
        self.assertEqual(response.status_code, 401)
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))
        self.assertEqual(response.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertNotIn('items', response.get_json())

    def test_non_admin_roles_are_rejected(self):
        for role in ('reader', 'creator', 'librarian', 'merchant'):
            with self.subTest(role=role), patch('app.current_user', return_value={'id': 7, 'role': role}):
                response = self.client.get('/api/setup/readiness')
                self.assertEqual(response.status_code, 403)
                self.assertNotIn('items', response.get_json())

    def test_admin_can_read_checklist_without_secret_values(self):
        with patch('app.current_user', return_value={'id': 1, 'role': 'admin'}):
            response = self.client.get('/api/setup/readiness')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('items', payload)
        self.assertIn('scope', payload)
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))
        self.assertNotIn('SECRET_KEY', response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
