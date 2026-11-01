import unittest
from commercial_readiness import valid_public_origin

class PublicOriginTests(unittest.TestCase):
    def test_valid_public_https_origin(self):
        self.assertTrue(valid_public_origin('https://books.example.com'))
        self.assertTrue(valid_public_origin('https://books.example.com:443'))
        self.assertTrue(valid_public_origin('https://bücher.example.com'))

    def test_rejects_credentials_path_query_and_fragment(self):
        for url in ('https://user:pass@books.example.com', 'https://books.example.com/path',
                    'https://books.example.com?debug=1', 'https://books.example.com/#x'):
            with self.subTest(url=url):
                self.assertFalse(valid_public_origin(url))

    def test_rejects_local_addresses_and_bad_ports(self):
        for url in ('https://localhost', 'https://127.0.0.1', 'https://[::1]',
                    'https://books.local', 'https://books.example.com:444',
                    'http://books.example.com', 'https://-bad.example.com'):
            with self.subTest(url=url):
                self.assertFalse(valid_public_origin(url))

    def test_rejects_reserved_and_internal_dns_suffixes(self):
        for url in (
            'https://shop.example.test',
            'https://shop.example.invalid',
            'https://shop.example.example',
            'https://books.internal',
            'https://books.corp.local',
            'https://books.home.arpa',
            'https://books.lan',
            'https://service.onion',
        ):
            with self.subTest(url=url):
                self.assertFalse(valid_public_origin(url))

    def test_rejects_malformed_values(self):
        for url in ('', ' https://books.example.com', 'https://books.example.com:bad', None):
            with self.subTest(url=url):
                self.assertFalse(valid_public_origin(url))
