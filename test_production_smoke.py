"""Regression tests for fail-closed deployment smoke checks."""
import unittest
from unittest.mock import patch
import urllib.error
from production_smoke import check, run, MAX_SMOKE_BODY_BYTES


class FakeResponse:
    def __init__(self, status=200, headers=None, body=b'{}'):
        self.status = status
        self.headers = headers or {}
        self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit): return self.body[:limit]


class FakeOpener:
    def __init__(self, response): self.response = response
    def open(self, request, timeout): return self.response


class ProductionSmokeTests(unittest.TestCase):
    def test_clean_https_origin_required(self):
        for url in ('http://example.com', 'https://user:pass@example.com',
                    'https://example.com/path', 'https://example.com/?x=1'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                run(url)

    def test_redirect_is_reported_not_followed(self):
        handler = __import__('production_smoke')._NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, 'Found', {}, 'https://elsewhere.example'))

    def test_response_size_limit(self):
        response = FakeResponse(body=b'x' * (MAX_SMOKE_BODY_BYTES + 1))
        with patch('urllib.request.build_opener', return_value=FakeOpener(response)):
            with self.assertRaisesRegex(ValueError, 'size limit'):
                check('https://example.com', '/api/health')

    def test_http_error_status_preserved(self):
        response = FakeResponse(status=503, body=b'{"status":"unavailable"}')
        error = urllib.error.HTTPError('https://example.com/api/ready', 503, 'Unavailable', {}, None)
        error.headers = {'Content-Type': 'application/json'}
        error.read = lambda limit: b'{"status":"unavailable"}'
        error.__enter__ = lambda self: self
        error.__exit__ = lambda *args: False
        with patch('urllib.request.build_opener', return_value=FakeOpener(error)):
            status, headers, body = check('https://example.com', '/api/ready')
        self.assertEqual(status, 503)
        self.assertEqual(body, b'{"status":"unavailable"}')


if __name__ == '__main__':
    unittest.main()
