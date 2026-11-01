import unittest
from safe_redirect import safe_local_return_url


class SafeLocalRedirectTests(unittest.TestCase):
    def test_allows_same_origin_path_query_and_fragment(self):
        self.assertEqual(
            safe_local_return_url('https://libra.example/books?q=math#top', 'libra.example', 'https'),
            '/books?q=math#top',
        )

    def test_rejects_external_host(self):
        self.assertEqual(safe_local_return_url('https://evil.example/phish', 'libra.example', 'https'), '/')

    def test_rejects_protocol_relative_and_userinfo_tricks(self):
        self.assertEqual(safe_local_return_url('//evil.example/phish', 'libra.example', 'https'), '/')
        self.assertEqual(safe_local_return_url('https://libra.example@evil.example/phish', 'libra.example', 'https'), '/')

    def test_rejects_scheme_mismatch_and_non_http_schemes(self):
        self.assertEqual(safe_local_return_url('http://libra.example/path', 'libra.example', 'https'), '/')
        self.assertEqual(safe_local_return_url('javascript:alert(1)', 'libra.example', 'https'), '/')

    def test_rejects_control_characters_and_backslashes(self):
        self.assertEqual(safe_local_return_url('https://libra.example/ok\r\nLocation: https://evil.example', 'libra.example', 'https'), '/')
        self.assertEqual(safe_local_return_url('https://libra.example\\@evil.example/path', 'libra.example', 'https'), '/')

    def test_invalid_or_missing_referrer_falls_back_home(self):
        self.assertEqual(safe_local_return_url(None, 'libra.example', 'https'), '/')
        self.assertEqual(safe_local_return_url('/relative/path', 'libra.example', 'https'), '/')


if __name__ == '__main__':
    unittest.main()
