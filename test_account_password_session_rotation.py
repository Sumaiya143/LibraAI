"""Regression checks for password-change session safety and user feedback."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent

class PasswordSessionRotationTests(unittest.TestCase):
    def test_success_rotates_csrf_token_after_database_commit(self):
        source = (ROOT / 'account_privacy.py').read_text()
        handler = source.split("@account_bp.post('/account/password')", 1)[1]
        self.assertIn("session['_csrf'] = secrets.token_urlsafe(32)", handler)
        self.assertIn("if changed:", handler)
        self.assertLess(handler.index('conn.close()'), handler.index("session['_csrf'] = secrets.token_urlsafe(32)"))

    def test_success_and_failure_feedback_are_distinct(self):
        source = (ROOT / 'account_privacy.py').read_text()
        self.assertIn("flash('Password updated successfully. Other signed-in devices must sign in again.')", source)
        self.assertIn('except PasswordChangeError as exc:', source)
        self.assertIn('flash(str(exc))', source)

if __name__ == '__main__':
    unittest.main()
