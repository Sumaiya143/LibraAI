import unittest
from gateway_readiness import inspect_config

GOOD = {'LIBRAAI_ENV':'production', 'SECRET_KEY':'0123456789abcdefghijklmnopqrstuvwxyzABCDEF',
        'PUBLIC_BASE_URL':'https://books.example.org',
        'SSLCOMMERZ_STORE_ID':'merchant', 'SSLCOMMERZ_STORE_PASSWORD':'secret',
        'BKASH_USERNAME':'user', 'BKASH_PASSWORD':'pass', 'BKASH_APP_KEY':'key',
        'BKASH_APP_SECRET':'secret', 'SSLCOMMERZ_SANDBOX':'false', 'BKASH_SANDBOX':'false'}

class GatewayReadinessTests(unittest.TestCase):
    def test_valid_production_config(self):
        self.assertTrue(inspect_config(GOOD)['ready'])
    def test_sandbox_defaults_fail_closed(self):
        env={k:v for k,v in GOOD.items() if not k.endswith('_SANDBOX')}
        result=inspect_config(env)
        self.assertFalse(result['ready'])
        self.assertEqual(2, sum(not c['passed'] for c in result['checks']))
    def test_missing_credentials(self):
        env={**GOOD, 'BKASH_APP_SECRET':''}
        self.assertFalse(inspect_config(env)['ready'])
    def test_url_rejects_insecure_or_credentials(self):
        for url in ('http://books.example.org','https://user:pw@books.example.org','https://books.example.org/path','https://localhost','https://books.example.org/?token=abc'):
            with self.subTest(url=url):
                self.assertFalse(inspect_config({**GOOD, 'PUBLIC_BASE_URL':url})['ready'])
    def test_rejects_private_ip_and_local_callback_origins(self):
        for url in ('https://192.168.1.10', 'https://10.0.0.1',
                    'https://127.0.0.1', 'https://[::1]',
                    'https://gateway.local', 'https://gateway.internal',
                    'https://example.test', 'https://example.invalid',
                    'https://example.org:8443', 'https://-bad.example.org'):
            with self.subTest(url=url):
                self.assertFalse(inspect_config({**GOOD, 'PUBLIC_BASE_URL':url})['ready'])

    def test_invalid_url_port_fails_cleanly(self):
        for url in ('https://example.org:bad', 'https://example.org:99999',
                    'https://[not-ipv6]'):
            with self.subTest(url=url):
                self.assertFalse(inspect_config({**GOOD, 'PUBLIC_BASE_URL':url})['ready'])

    def test_standard_https_port_is_allowed(self):
        self.assertTrue(inspect_config({**GOOD, 'PUBLIC_BASE_URL':'https://books.example.org:443'})['ready'])

    def test_never_exposes_secrets(self):
        result=str(inspect_config({**GOOD,'BKASH_APP_SECRET':'SENSITIVE_VALUE_123'}))
        self.assertNotIn('SENSITIVE_VALUE_123', result)
    def test_weak_session_secret(self):
        self.assertFalse(inspect_config({**GOOD,'SECRET_KEY':'x'*40})['ready'])
    def test_invalid_sandbox_value(self):
        self.assertFalse(inspect_config({**GOOD,'BKASH_SANDBOX':'maybe'})['ready'])

    def test_canonical_public_url_is_accepted(self):
        env={k:v for k,v in GOOD.items() if k!='PUBLIC_BASE_URL'}
        self.assertTrue(inspect_config({**env,'LIBRAAI_PUBLIC_URL':'https://books.example.org'})['ready'])

    def test_conflicting_public_url_aliases_fail_closed(self):
        self.assertFalse(inspect_config({**GOOD,'LIBRAAI_PUBLIC_URL':'https://other.example.org'})['ready'])

    def test_matching_public_url_aliases_are_accepted(self):
        self.assertTrue(inspect_config({**GOOD,'LIBRAAI_PUBLIC_URL':'https://books.example.org/'})['ready'])

if __name__=='__main__': unittest.main()
