import unittest
from payment_origin import validate_public_origin
from payment_providers import GatewayError

class PaymentOriginTests(unittest.TestCase):
    def test_valid_origin(self):
        self.assertEqual(validate_public_origin('https://books.example.org'), 'https://books.example.org')
    def test_valid_trailing_slash(self):
        self.assertEqual(validate_public_origin('https://books.example.org/'), 'https://books.example.org')

    def test_normalizes_case_and_internationalized_domains(self):
        self.assertEqual(validate_public_origin('https://BOOKS.EXAMPLE.ORG'), 'https://books.example.org')
        self.assertEqual(validate_public_origin('https://bücher.example.org'), 'https://xn--bcher-kva.example.org')

    def test_accepts_public_ip_literals(self):
        self.assertEqual(validate_public_origin('https://8.8.8.8'), 'https://8.8.8.8')
        self.assertEqual(validate_public_origin('https://[2606:4700:4700::1111]'), 'https://[2606:4700:4700::1111]')
    def test_rejects_reserved_and_internal_suffixes(self):
        for value in (
            'https://merchant.test',
            'https://merchant.invalid',
            'https://merchant.example',
            'https://merchant.localhost',
            'https://merchant.local',
            'https://merchant.internal',
            'https://merchant.onion',
            'https://service.home.arpa',
            'https://test',
        ):
            with self.subTest(value=value):
                with self.assertRaises(GatewayError):
                    validate_public_origin(value)

    def test_invalid_origins(self):
        for value in ('', 'http://books.example.org', 'https://books.example.org@evil.test',
                      'https://books.example.org/path', 'https://books.example.org/?x=1',
                      'https://books.example.org/#frag', 'https://books.example.org:abc',
                      'https://books.example.org:444', 'https://localhost',
                      ' https://books.example.org', 'https://books.example.org\\evil.test',
                      'https://localhost.localdomain', 'https://127.0.0.1',
                      'https://10.0.0.8', 'https://192.168.1.10',
                      'https://[::1]', 'https://[2001:db8::1]',
                      'https://singlelabel', 'https://bad_.example',
                      'https://bad..example', 'https://example.com.',
                      'https://999.999.999.999', 'https://example.com:444'):
            with self.subTest(value=value):
                with self.assertRaises(GatewayError): validate_public_origin(value)

if __name__ == '__main__': unittest.main()
