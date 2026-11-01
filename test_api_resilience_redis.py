import os, sys, types, unittest
from unittest.mock import patch
import api_resilience

class FakeRedisClient:
    def __init__(self): self.counts={}; self.ttls={}
    def eval(self, script, key_count, key, window):
        self.counts[key]=self.counts.get(key,0)+1; self.ttls[key]=int(window)
        return [self.counts[key],self.ttls[key]]
class FakeRedisModule:
    def __init__(self, client):
        self.client=client
        self.Redis=types.SimpleNamespace(from_url=lambda *args,**kwargs: self.client)

class RedisRateLimitTests(unittest.TestCase):
    def setUp(self): api_resilience.reset_rate_limits_for_tests()
    def test_redis_backend_shares_atomic_limit_and_returns_retry_after(self):
        client=FakeRedisClient()
        with patch.dict(os.environ, {'LIBRAAI_RATE_LIMIT_BACKEND':'redis','REDIS_URL':'redis://unit-test','SECRET_KEY':'stable-shared-test-secret-key-1234567890'}), patch.dict(sys.modules, {'redis':FakeRedisModule(client)}):
            results=[api_resilience.check_rate_limit('/login','POST','192.0.2.8',now=100) for _ in range(11)]
        self.assertTrue(all(x is None for x in results[:10]))
        self.assertEqual(results[10]['status'],429)
        self.assertGreaterEqual(results[10]['retry_after'],1)
    def test_redis_backend_fails_closed_when_url_missing(self):
        with patch.dict(os.environ, {'LIBRAAI_RATE_LIMIT_BACKEND':'redis'}, clear=False):
            os.environ.pop('REDIS_URL',None)
            result=api_resilience.check_rate_limit('/login','POST','192.0.2.9',now=100)
        self.assertEqual(result['status'],503)
    def test_unknown_backend_fails_closed(self):
        with patch.dict(os.environ, {'LIBRAAI_RATE_LIMIT_BACKEND':'memcached'}):
            result=api_resilience.check_rate_limit('/login','POST','192.0.2.10',now=100)
        self.assertEqual(result['status'],503)

if __name__=='__main__': unittest.main()
