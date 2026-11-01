import unittest
from production_preflight import valid_public_url, inspect

class ProductionPublicURLTests(unittest.TestCase):
    def test_accepts_valid_https_domains_and_ip_addresses(self):
        for value in (
            'https://example.com',
            'https://example.com/',
            'https://8.8.8.8',
            'https://[2606:4700:4700::1111]',
            'https://bücher.example.com',
        ):
            with self.subTest(value=value):
                self.assertTrue(valid_public_url(value))

    def test_rejects_non_https_and_malformed_values(self):
        for value in (
            '', 'http://example.com', 'https://', 'https://production',
            'https://localhost', 'https://user:password@example.com',
            'https://example.com?next=https://evil.example',
            'https://example.com#fragment', 'https://example.com:99999',
            'https://bad host.example', 'https://-bad.example',
            'https://bad!.example', 'https://bad_.example',
            'https://bad..example', 'https://bad-.example',
            'https://999.999.999.999', 'https://127.0.0.1',
            'https://192.168.1.10', 'https://[::1]',
            'https://[2001:db8::1]', 'https://example.com.',
        ):
            with self.subTest(value=value):
                self.assertFalse(valid_public_url(value))

    def test_rejects_invalid_dns_label_characters(self):
        for value in (
            'https://bad!.example', 'https://bad_.example',
            'https://bad..example', 'https://bad-.example',
            'https://example.com.',
            'https://app.example.com/reader',
            'https://example.com:8443',
            'https://shop.example.test',
            'https://shop.example.invalid',
            'https://books.internal',
            'https://books.home.arpa',
            'https://service.onion',
        ):
            with self.subTest(value=value):
                self.assertFalse(valid_public_url(value))

    def test_rejects_non_public_ip_literals(self):
        for value in (
            'https://127.0.0.1', 'https://192.168.1.10',
            'https://999.999.999.999', 'https://[::1]',
            'https://[2001:db8::1]',
        ):
            with self.subTest(value=value):
                self.assertFalse(valid_public_url(value))

    def test_preflight_marks_malformed_https_url_failed(self):
        result = inspect({
            'LIBRAAI_ENV': 'production',
            'SECRET_KEY': 'S' * 64,
            'LIBRAAI_DEBUG': '0',
            'LIBRAAI_PUBLIC_URL': 'https://',
            'LIBRAAI_DB_PATH': '/data/libraai.db',
        })
        self.assertFalse(next(c for c in result['checks'] if c['check'] == 'https')['passed'])
        self.assertFalse(result['ready'])

if __name__ == '__main__':
    unittest.main()
