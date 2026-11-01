"""Regression tests for credential-bound login sessions."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent

class CredentialSessionInvalidationTests(unittest.TestCase):
    def test_current_user_checks_credential_fingerprint_and_clears_stale_session(self):
        source = (ROOT / 'app.py').read_text()
        block = source.split('def current_user():', 1)[1].split('\ndef login_required', 1)[0]
        self.assertIn("session.get('_credential_fingerprint')", block)
        self.assertIn("credential_fingerprint(u['password'])", block)
        self.assertIn('hmac.compare_digest', block)
        self.assertIn('session.clear()', block)

    def test_login_and_signup_bind_session_to_the_actual_stored_hash(self):
        source = (ROOT / 'app.py').read_text()
        self.assertGreaterEqual(source.count("session['_credential_fingerprint'] = credential_fingerprint("), 2)
        signup = source.split("@app.route('/signup'", 1)[1] if "@app.route('/signup'" in source else source.split("@app.route('/register'", 1)[1]
        self.assertIn("create_account(", signup)
        self.assertIn("PUBLIC_ACCOUNT_TYPES[account_type]", signup)
        self.assertIn("credential_fingerprint(password_hash)", signup)

    def test_account_endpoints_reject_stale_sessions(self):
        source = (ROOT / 'account_privacy.py').read_text()
        self.assertIn('def _valid_credential_session(uid):', source)
        self.assertGreaterEqual(source.count('_valid_credential_session('), 4)

    def test_password_change_refreshes_current_session_binding(self):
        source = (ROOT / 'account_privacy.py').read_text()
        self.assertIn("session['_credential_fingerprint'] = sha256(str(row[0]).encode('utf-8')).hexdigest()", source)
        self.assertIn('Other signed-in devices must sign in again.', source)

if __name__ == '__main__':
    unittest.main()
