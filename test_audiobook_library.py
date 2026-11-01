import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

# The build container may omit Flask; stub only its decorator surface so pure
# licensing/schema helpers remain testable without running HTTP endpoints.
_flask_test_stub_installed = False
try:
    import flask  # noqa: F401
except ModuleNotFoundError:
    _flask_test_stub_installed = True
    import sys, types
    class _Blueprint:
        def __init__(self, *args, **kwargs): pass
        def get(self, *args, **kwargs): return lambda fn: fn
        def post(self, *args, **kwargs): return lambda fn: fn
        def before_request(self, *args, **kwargs): return lambda fn: fn
    stub = types.ModuleType('flask')
    stub.Blueprint = _Blueprint
    stub.abort = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('abort called in pure helper test'))
    stub.current_app = types.SimpleNamespace(config={}, logger=types.SimpleNamespace(exception=lambda *a, **k: None))
    stub.jsonify = lambda *a, **k: None
    stub.request = types.SimpleNamespace()
    stub.send_file = lambda *a, **k: None
    stub.session = {}
    sys.modules['flask'] = stub
from audiobook_library import AUDIO_TYPES, _license_valid, setup

# Keep the fallback scoped to importing this pure-helper module. Leaving it in
# sys.modules masks the real missing dependency and breaks unrelated tests.
if _flask_test_stub_installed:
    import sys
    sys.modules.pop('flask', None)

class AudioLicenseTests(unittest.TestCase):
    def test_audio_types_are_explicit(self):
        self.assertEqual(AUDIO_TYPES['.mp3'], 'audio/mpeg')
        self.assertIn('.m4a', AUDIO_TYPES)
        self.assertNotIn('.exe', AUDIO_TYPES)

    def test_license_requires_active_status(self):
        base = {'active': 1, 'license_status': 'active', 'license_expires_at': None}
        self.assertTrue(_license_valid(base))
        self.assertFalse(_license_valid({**base, 'active': 0}))
        self.assertFalse(_license_valid({**base, 'license_status': 'revoked'}))

    def test_expired_and_invalid_dates_fail_closed(self):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        self.assertFalse(_license_valid({'active': 1, 'license_status': 'active', 'license_expires_at': past}))
        self.assertFalse(_license_valid({'active': 1, 'license_status': 'active', 'license_expires_at': 'not-a-date'}))

    def test_schema_is_idempotent(self):
        with tempfile.NamedTemporaryFile(suffix='.db') as tmp:
            def connect():
                c = sqlite3.connect(tmp.name)
                c.execute('PRAGMA foreign_keys=ON')
                c.execute('CREATE TABLE IF NOT EXISTS books(id INTEGER PRIMARY KEY, title TEXT)')
                return c
            setup(connect)
            setup(connect)
            c = connect()
            columns = {r[1] for r in c.execute('PRAGMA table_info(audiobook_assets)')}
            c.close()
            self.assertTrue({'book_id','storage_key','rights_holder','license_reference','license_status','sha256_hex'}.issubset(columns))

if __name__ == '__main__':
    unittest.main()
