import unittest
from launch_audit import audit

class LaunchAuditTests(unittest.TestCase):
    def test_empty_configuration_blocks_launch(self):
        result = audit(env={})
        self.assertFalse(result['production_ready'])
        self.assertEqual(result['total'], 12)
        self.assertFalse(next(x for x in result['checks'] if x['id']=='payment_e2e')['passed'])

    def test_credential_flags_cannot_certify_launch(self):
        env = {'LIBRA_HTTPS':'1', 'PUBLIC_BASE_URL':'https://example.com', 'LIBRAAI_AUTH_THROTTLE':'1',
               'SSLCZ_STORE_ID':'demo', 'SSLCZ_STORE_PASSWORD':'demo', 'BKASH_APP_KEY':'demo',
               'BKASH_APP_SECRET':'demo', 'BKASH_USERNAME':'demo', 'BKASH_PASSWORD':'demo',
               'LIBRA_BACKUP_VERIFIED':'1'}
        result = audit(env=env)
        self.assertFalse(result['production_ready'])
        self.assertFalse(next(x for x in result['checks'] if x['id']=='security_audit')['passed'])

    def test_non_https_public_url_fails(self):
        result = audit(env={'LIBRA_HTTPS':'1','PUBLIC_BASE_URL':'http://example.com'})
        self.assertFalse(next(x for x in result['checks'] if x['id']=='https')['passed'])

if __name__ == '__main__':
    unittest.main()
