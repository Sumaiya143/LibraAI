import unittest, logging, json
from api_resilience import check_rate_limit, client_fingerprint, reset_rate_limits_for_tests, JsonRequestFormatter

class ApiResilienceTests(unittest.TestCase):
    def setUp(self): reset_rate_limits_for_tests()
    def test_sensitive_post_is_limited(self):
        for _ in range(10):
            self.assertIsNone(check_rate_limit('/login','POST','127.0.0.1',1000))
        blocked = check_rate_limit('/login','POST','127.0.0.1',1000)
        self.assertEqual(blocked['error'],'rate_limit_exceeded')
        self.assertGreaterEqual(blocked['retry_after'],1)
    def test_limit_expires_after_window(self):
        for _ in range(10): check_rate_limit('/login','POST','127.0.0.1',1000)
        self.assertIsNone(check_rate_limit('/login','POST','127.0.0.1',1061))
    def test_get_requests_are_not_rate_limited_by_write_policy(self):
        for _ in range(50): self.assertIsNone(check_rate_limit('/login','GET','127.0.0.1',1000))
    def test_other_clients_have_separate_buckets(self):
        for _ in range(10): check_rate_limit('/login','POST','127.0.0.1',1000)
        self.assertIsNone(check_rate_limit('/login','POST','127.0.0.2',1000))
    def test_fingerprint_does_not_echo_ip(self):
        value=client_fingerprint('203.0.113.9')
        self.assertNotIn('203.0.113.9',value)
        self.assertEqual(len(value),24)
    def test_ai_endpoint_is_limited(self):
        for _ in range(20): self.assertIsNone(check_rate_limit('/api/ai','POST','client',5))
        self.assertIsNotNone(check_rate_limit('/api/ai','POST','client',5))
    def test_unmatched_paths_are_not_limited(self):
        self.assertIsNone(check_rate_limit('/api/catalog/search','POST','client',5))
    def test_json_login_api_is_rate_limited(self):
        for _ in range(8):
            self.assertIsNone(check_rate_limit('/api/login','POST','client',5))
        self.assertEqual(check_rate_limit('/api/login','POST','client',5)['error'],'rate_limit_exceeded')

    def test_auth_aliases_are_rate_limited(self):
        for _ in range(5):
            self.assertIsNone(check_rate_limit('/api/auth/signup','POST','client',5))
        self.assertEqual(check_rate_limit('/api/auth/signup','POST','client',5)['error'],'rate_limit_exceeded')

    def test_json_request_log_formatter_only_emits_explicit_safe_fields(self):
        record = logging.LogRecord('test', logging.INFO, __file__, 1, 'private@example.com 203.0.113.9', (), None)
        record.event_name = 'request_complete'; record.request_id = 'server-generated-id'
        record.method = 'GET'; record.route = '/account'; record.status = 200
        record.duration_ms = 4.2; record.client_fingerprint = client_fingerprint('203.0.113.9')
        rendered = JsonRequestFormatter().format(record)
        payload = json.loads(rendered)
        self.assertEqual(payload['request_id'], 'server-generated-id')
        self.assertNotIn('private@example.com', rendered)
        self.assertNotIn('203.0.113.9', rendered)
        self.assertEqual(payload['route'], '/account')

if __name__ == '__main__': unittest.main()
