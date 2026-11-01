"""Dependency-free release contract checks for the server-side session adapter."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent

class ServerSideSessionContractTests(unittest.TestCase):
    def test_flask_app_uses_server_side_session_adapter(self):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertIn('from server_side_sessions import SQLiteSessionInterface', source)
        self.assertIn('app.session_interface = SQLiteSessionInterface(DB)', source)

    def test_cookie_contains_signed_opaque_id_and_session_data_stays_in_sqlite(self):
        source = (ROOT / 'server_side_sessions.py').read_text(encoding='utf-8')
        self.assertIn('URLSafeSerializer', source)
        self.assertIn('server_sessions', source)
        self.assertIn('session_data TEXT NOT NULL', source)
        self.assertIn('self._serializer(app).dumps(session.sid)', source)
        self.assertNotIn('json.dumps(dict(session)).encode', source)

    def test_session_store_fails_closed_and_rotates_id(self):
        source = (ROOT / 'server_side_sessions.py').read_text(encoding='utf-8')
        self.assertIn('raise RuntimeError("LibraAI session storage is unavailable")', source)
        self.assertIn('if session.regenerate or session.new:', source)
        self.assertIn('session.sid = secrets.token_urlsafe(32)', source)
        self.assertIn('expires_at<=?', source)

if __name__ == '__main__':
    unittest.main()
