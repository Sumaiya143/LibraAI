import io
import json
import unittest
from email.message import Message
from live_site_probe import probe

class FakeResponse:
    status = 200
    def __init__(self, body):
        self.body = body
        self.headers = Message()
        for key in ('X-Content-Type-Options', 'Content-Security-Policy', 'Strict-Transport-Security'):
            self.headers[key] = 'enabled'
    def read(self, limit): return self.body
    def __enter__(self): return self
    def __exit__(self, *args): pass

class ProbeTests(unittest.TestCase):
    def test_rejects_local_http_without_network(self):
        self.assertFalse(probe('http://localhost:8000')['passed'])
    def test_rejects_https_with_credentials(self):
        self.assertFalse(probe('https://user:password@example.com')['passed'])
    def test_passes_read_only_health_checks(self):
        def opener(req):
            if req.full_url.endswith('/api/ready'):
                return FakeResponse(json.dumps({'status':'ready','scope':'database-and-application-only'}).encode())
            return FakeResponse(b'{"status":"ok"}')
        self.assertTrue(probe('https://books.example.com', opener)['passed'])
    def test_ready_does_not_mean_commercial_verified(self):
        def opener(req):
            return FakeResponse(b'{"status":"ready","scope":"all-systems"}')
        result = probe('https://books.example.com', opener)
        self.assertFalse(result['passed'])
        self.assertTrue(result['limitations'])
    def test_missing_security_headers_fail(self):
        def opener(req):
            response = FakeResponse(b'{"status":"ready","scope":"database-and-application-only"}')
            del response.headers['Strict-Transport-Security']
            return response
        self.assertFalse(probe('https://books.example.com', opener)['passed'])
    def test_network_failure_does_not_claim_success(self):
        from urllib.error import URLError
        def opener(req): raise URLError('offline')
        self.assertFalse(probe('https://books.example.com', opener)['passed'])

if __name__ == '__main__': unittest.main()

class RedirectSafetyTests(unittest.TestCase):
    def test_redirected_fake_response_is_rejected(self):
        class Redirected(FakeResponse):
            def geturl(self): return 'https://other.example.com/api/ready'
        def opener(req):
            return Redirected(b'{"status":"ready","scope":"database-and-application-only"}')
        self.assertFalse(probe('https://books.example.com', opener)['passed'])

    def test_default_opener_disables_redirects(self):
        from live_site_probe import NoRedirects
        from urllib.request import Request
        self.assertIsNone(NoRedirects().redirect_request(Request('https://example.com'), None, 302, 'redirect', {}, 'http://localhost/'))

    def test_oversized_response_rejected(self):
        def opener(req):
            return FakeResponse(b'x' * 65537)
        self.assertFalse(probe('https://books.example.com', opener)['passed'])
