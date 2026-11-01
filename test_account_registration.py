"""Regression coverage for role-aware registration and configured SQLite runtime."""
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from account_registration import AccountRegistrationError, validate_account


class AccountValidationTests(unittest.TestCase):
    def test_normalizes_identity(self):
        self.assertEqual(
            validate_account('  Customer  ', ' USER@Example.COM ', 'a secure password'),
            ('Customer', 'user@example.com', 'a secure password'),
        )

    def test_rejects_invalid_password_and_email(self):
        with self.assertRaises(AccountRegistrationError):
            validate_account('Customer', 'not-an-email', 'a secure password')
        with self.assertRaises(AccountRegistrationError):
            validate_account('Customer', 'user@example.com', 'short')


class AccountRuntimeTests(unittest.TestCase):
    def test_three_role_flows_and_configured_database(self):
        root = Path(__file__).resolve().parent
        script = textwrap.dedent(r'''
            import os, re, sqlite3
            from app import app

            def token(client, path):
                response = client.get(path)
                assert response.status_code == 200, (path, response.status_code)
                return re.search(r'name="_csrf" value="([^"]+)"', response.get_data(as_text=True)).group(1)

            def signup(client, email, kind='customer', name='Test User', store_name=None):
                data = {
                    '_csrf': token(client, '/register'), 'name': name, 'email': email,
                    'password': 'correct horse battery', 'account_type': kind,
                }
                if store_name is not None:
                    data['store_name'] = store_name
                return client.post('/register', data=data, follow_redirects=False)

            def login(client, email, password='demo123'):
                return client.post('/login', data={
                    '_csrf': token(client, '/login'), 'email': email, 'password': password,
                }, follow_redirects=False)

            with app.test_client() as client:
                landing = client.get('/')
                assert landing.status_code == 200
                assert 'More than books.' in landing.get_data(as_text=True)
                assert 'Administrator sign in' in landing.get_data(as_text=True)
                assert signup(client, 'customer@example.com').status_code == 302
                for path in ('/library', '/learning/', '/research/', '/workspace/'):
                    assert client.get(path).status_code == 200, path
                assert client.get('/creator').status_code == 403
                assert client.get('/admin/users/new').status_code == 403
                response = client.get('/admin')
                assert response.status_code == 200
                assert 'Library Admin is for administrators' in response.get_data(as_text=True)
                assert client.get('/admin/dashboard').status_code == 200

            with app.test_client() as client:
                assert signup(client, 'seller@example.com', 'seller', 'Test Seller').status_code == 302
                assert client.get('/creator').status_code == 200
                response = client.get('/admin')
                assert response.status_code == 200
                assert 'Library Admin is for administrators' in response.get_data(as_text=True)
                assert client.get('/admin/users/new').status_code == 403

            with app.test_client() as client:
                assert signup(client, 'merchant@example.com', 'merchant', 'Test Merchant', 'Merchant Books').status_code == 302
                response = client.get('/creator')
                assert response.status_code == 200
                assert 'Merchant Books' in response.get_data(as_text=True)

            with app.test_client() as client:
                assert login(client, 'admin@libra.ai').status_code == 302
                response = client.get('/admin/dashboard')
                assert response.status_code == 200
                dashboard = response.get_data(as_text=True)
                assert 'Library Admin Dashboard' in dashboard
                assert 'Catalog titles' in dashboard
                assert 'Recent activity' in dashboard
                response = client.post('/admin/users/new', data={
                    '_csrf': token(client, '/admin/users/new'), 'name': 'Second Admin',
                    'email': 'admin2@example.com', 'password': 'another secure password',
                    'account_type': 'admin',
                }, follow_redirects=False)
                assert response.status_code == 302, response.status_code

            with app.test_client() as client:
                # Public signup must never accept a privilege-escalating role.
                assert signup(client, 'intruder@example.com', 'admin').status_code == 200

            with app.test_client() as client:
                # Wishlist state must be account-bound and removable, not just a frontend toggle.
                assert login(client, 'reader@libra.ai').status_code == 302
                catalog = client.get('/api/books?q=Atomic%20Habits')
                assert catalog.status_code == 200
                book_id = catalog.get_json()[0]['id']
                status = client.get(f'/api/wishlist/{book_id}')
                assert status.status_code == 200 and status.get_json()['saved'] is False
                added = client.post(f'/action/wishlist/{book_id}', data={'_csrf': token(client, '/login')}, follow_redirects=False)
                assert added.status_code == 302
                status = client.get(f'/api/wishlist/{book_id}')
                assert status.status_code == 200 and status.get_json()['saved'] is True
                removed = client.post(f'/action/wishlist/{book_id}/remove', data={'_csrf': token(client, '/login')}, follow_redirects=False)
                assert removed.status_code == 302
                status = client.get(f'/api/wishlist/{book_id}')
                assert status.status_code == 200 and status.get_json()['saved'] is False

            with sqlite3.connect(os.environ['LIBRAAI_DB_PATH']) as conn:
                roles = dict(conn.execute(
                    "SELECT email,role FROM users WHERE email LIKE '%@example.com'"
                ))
                assert roles == {
                    'customer@example.com': 'reader',
                    'seller@example.com': 'creator',
                    'merchant@example.com': 'creator',
                    'admin2@example.com': 'admin',
                }, roles
                profiles = dict(conn.execute(
                    "SELECT users.email,merchant_profiles.store_name FROM merchant_profiles JOIN users ON users.id=merchant_profiles.user_id WHERE users.email LIKE '%@example.com'"
                ))
                assert profiles == {
                    'seller@example.com': 'Test Seller',
                    'merchant@example.com': 'Merchant Books',
                }, profiles
                assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                assert not conn.execute('PRAGMA foreign_key_check').fetchall()
        ''')
        with tempfile.TemporaryDirectory() as temp:
            env = os.environ.copy()
            env['LIBRAAI_DB_PATH'] = str(Path(temp) / 'accounts.db')
            env.pop('LIBRAAI_ENV', None)
            result = subprocess.run(
                [sys.executable, '-c', script], cwd=root, env=env,
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class AccountInsertTests(unittest.TestCase):
    def setUp(self):
        self.conn = __import__('sqlite3').connect(':memory:')
        self.conn.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT, username TEXT, email TEXT UNIQUE, password TEXT, role TEXT, plan TEXT)')
        self.conn.execute('CREATE UNIQUE INDEX users_username_ci ON users(lower(username)) WHERE username IS NOT NULL')
        self.conn.execute('CREATE TABLE merchant_profiles(user_id INTEGER PRIMARY KEY, store_name TEXT)')

    def tearDown(self):
        self.conn.close()

    def create(self, name, email, username=None):
        from account_registration import create_account
        return create_account(self.conn, name, email, 'a sufficiently long password', 'reader', 'Free', lambda value: 'hashed:' + value, username=username)

    def test_same_display_name_gets_unique_generated_usernames(self):
        self.create('Same Reader', 'one@example.org')
        self.create('Same Reader', 'two@example.org')
        names = [row[0] for row in self.conn.execute('SELECT username FROM users ORDER BY id')]
        self.assertEqual(names, ['same.reader', 'same.reader2'])

    def test_email_uniqueness_is_case_insensitive(self):
        self.create('First Reader', 'Reader@Example.org')
        with self.assertRaises(AccountRegistrationError):
            self.create('Second Reader', 'reader@example.org')

    def test_explicit_duplicate_username_is_rejected(self):
        self.create('First Reader', 'one@example.org', 'reader_one')
        with self.assertRaises(AccountRegistrationError):
            self.create('Second Reader', 'two@example.org', 'READER_ONE')


if __name__ == '__main__':
    unittest.main()
