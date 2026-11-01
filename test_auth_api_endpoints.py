"""End-to-end regression tests for the production Flask JSON auth contract."""
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class AuthApiEndpointTests(unittest.TestCase):
    def test_signup_login_username_email_role_csrf_and_logout(self):
        root = Path(__file__).resolve().parent
        script = textwrap.dedent(r'''
            from app import app
            app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
            client = app.test_client()

            def csrf(c=client):
                r = c.get('/api/csrf')
                assert r.status_code == 200, r.status_code
                return r.get_json()['csrfToken']

            def post(path, payload, token=None, c=client):
                return c.post(path, json=payload, headers={'X-CSRF-Token': token or csrf(c)})

            # JSON POSTs without a CSRF token are rejected before touching auth state.
            assert client.post('/api/signup', json={'name':'No CSRF','email':'x@example.com','password':'a secure password','role':'customer'}).status_code == 400

            signup = post('/api/signup', {
                'name':'Same Name', 'username':'reader_one', 'email':'Reader.One@Example.com',
                'password':'correct horse battery', 'role':'customer'
            })
            assert signup.status_code == 201, signup.get_json()
            data = signup.get_json()
            assert data['user']['role'] == 'reader'
            assert data['user']['email'] == 'reader.one@example.com'
            assert data['user']['username'] == 'reader_one'
            assert client.get('/api/me').get_json()['id'] == data['user']['id']

            # Logout is CSRF-protected, clears the session and is idempotent.
            assert post('/api/logout', {}).status_code == 200
            assert client.get('/api/me').get_json() is None

            # Login by username and email both work, case-insensitively.
            by_username = post('/api/login', {'identifier':'READER_ONE','password':'correct horse battery'})
            assert by_username.status_code == 200, by_username.get_json()
            assert by_username.get_json()['user']['role'] == 'reader'
            assert post('/api/logout', {}).status_code == 200
            by_email = post('/api/login', {'email':'READER.ONE@EXAMPLE.COM','password':'correct horse battery'})
            assert by_email.status_code == 200, by_email.get_json()

            # Duplicate normalized email and username are rejected without leaking internals.
            dup_email = post('/api/signup', {'name':'Another','username':'another_user','email':'reader.one@example.com','password':'another secure password','role':'merchant'})
            assert dup_email.status_code == 409, dup_email.get_json()
            dup_username = post('/api/signup', {'name':'Another','username':'reader_one','email':'another@example.com','password':'another secure password','role':'merchant'})
            assert dup_username.status_code == 409, dup_username.get_json()

            # Auto-generated usernames do not collide for same-name accounts.
            assert post('/api/logout', {}).status_code == 200
            first = post('/api/signup', {'name':'Common Seller','email':'seller1@example.com','password':'another secure password','role':'seller'})
            assert first.status_code == 201, first.get_json()
            assert first.get_json()['user']['role'] == 'creator'
            assert first.get_json()['user']['username'] == 'common.seller'
            assert post('/api/logout', {}).status_code == 200
            second = post('/api/signup', {'name':'Common Seller','email':'seller2@example.com','password':'another secure password','role':'merchant'})
            assert second.status_code == 201, second.get_json()
            assert second.get_json()['user']['username'] == 'common.seller2'

            # Public signup cannot self-assign privileged roles.
            assert post('/api/signup', {'name':'Admin','email':'badadmin@example.com','password':'another secure password','role':'admin'}).status_code == 400

            # Dashboard compatibility redirect no longer points to a missing route.
            assert client.get('/dashboard').status_code in (301, 302)
        ''')
        with tempfile.TemporaryDirectory() as temp:
            env = os.environ.copy()
            env['LIBRAAI_DB_PATH'] = str(Path(temp) / 'auth-api.db')
            env['LIBRAAI_ENV'] = 'test'
            env.pop('SECRET_KEY', None)
            result = subprocess.run([sys.executable, '-c', script], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class AuthApiSourceContractTests(unittest.TestCase):
    def test_production_app_exposes_json_auth_and_role_redirects(self):
        root = Path(__file__).resolve().parent
        source = (root / 'app.py').read_text(encoding='utf-8')
        for route in ("@app.post('/api/signup')", "@app.post('/api/login')", "@app.get('/api/me')", "@app.post('/api/logout')", "@app.get('/api/csrf')"):
            self.assertIn(route, source)
        self.assertIn("'creator': '/creator'", source)
        self.assertIn("'admin': '/admin/dashboard'", source)
        self.assertIn("'librarian': '/librarian'", source)
        self.assertIn("request.headers.get('X-CSRF-Token')", source)

    def test_account_frontend_fetches_csrf_and_accepts_username_or_email(self):
        root = Path(__file__).resolve().parent
        script = (root / 'static' / 'account.js').read_text(encoding='utf-8')
        markup = (root / 'static' / 'account.html').read_text(encoding='utf-8')
        self.assertIn("fetch('/api/csrf'", script)
        self.assertIn("'X-CSRF-Token': csrfToken", script)
        self.assertIn("identity.name = signUp ? 'email' : 'identifier'", script)
        self.assertIn('id="username-field"', markup)
        self.assertIn('name="role"', markup)


if __name__ == '__main__':
    unittest.main()
