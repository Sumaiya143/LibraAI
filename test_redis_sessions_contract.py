from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parent
class RedisSessionContractTests(unittest.TestCase):
    def test_redis_session_backend_is_fail_closed_and_ttl_bounded(self):
        source=(ROOT/'redis_sessions.py').read_text()
        self.assertIn('self.client.ping()',source)
        self.assertIn('set(self._key(session.sid), payload, ex=ttl)',source)
        self.assertIn('refusing client-side fallback',source)
        self.assertIn('URLSafeSerializer',source)
    def test_multi_instance_requires_shared_session_and_rate_limit(self):
        source=(ROOT/'app.py').read_text()
        self.assertIn("_session_backend != 'redis' or _rate_backend != 'redis'",source)
        self.assertIn('primary SQLite database still needs migration to PostgreSQL',source)
if __name__=='__main__': unittest.main()
