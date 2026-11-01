import unittest
from setup_readiness import build_readiness, build_public_notices, readiness_access_status

class SetupReadinessTests(unittest.TestCase):
    def test_readiness_is_admin_only(self):
        self.assertEqual(readiness_access_status(None), 401)
        self.assertEqual(readiness_access_status({'role': 'reader'}), 403)
        self.assertEqual(readiness_access_status({'role': 'creator'}), 403)
        self.assertEqual(readiness_access_status({'role': 'admin'}), 200)

    def test_default_config_never_claims_launch_ready(self):
        report = build_readiness({})
        self.assertFalse(report['launch_ready'])
        self.assertGreater(report['open_count'], 0)
        self.assertIn('creator-payouts', {item['id'] for item in report['items']})

    def test_readiness_contains_no_secret_values(self):
        env = {'SSLCOMMERZ_STORE_ID':'do-not-leak-store-id', 'SSLCOMMERZ_STORE_PASSWORD':'do-not-leak-password',
               'BKASH_USERNAME':'user', 'BKASH_PASSWORD':'pass', 'BKASH_APP_KEY':'key', 'BKASH_APP_SECRET':'secret'}
        rendered = repr(build_readiness(env))
        self.assertNotIn('do-not-leak', rendered)
        self.assertNotIn('pass', rendered)
        self.assertNotIn('secret', rendered)


    def test_public_notices_are_actionable_without_exposing_provider_configuration(self):
        report = build_public_notices({'LIBRAAI_ENV':'production', 'SSLCOMMERZ_STORE_PASSWORD':'must-not-leak'})
        ids = {item['id'] for item in report['items']}
        self.assertIn('payments', ids)
        self.assertIn('creator-payouts', ids)
        self.assertIn('production-acceptance', ids)
        self.assertNotIn('must-not-leak', repr(report))
        self.assertTrue(all(item['href'].startswith('/') for item in report['items']))

    def test_public_notices_hide_attested_items_but_keep_unimplemented_payout_notice(self):
        env = {
          'LIBRAAI_LIVE_PAYMENT_E2E_VERIFIED':'yes','LIBRAAI_GATEWAY_E2E_VERIFIED':'yes',
          'LIBRAAI_PAYOUT_LIVE_E2E_VERIFIED':'yes','LIBRAAI_LICENSE_RIGHTS_VERIFIED':'yes',
          'LIBRAAI_CONTENT_RIGHTS_VERIFIED':'yes','LIBRAAI_SECURITY_REVIEW_PASSED':'yes',
          'LIBRAAI_SECURITY_REVIEW_VERIFIED':'yes','LIBRAAI_BACKUP_RESTORE_VERIFIED':'yes',
          'LIBRAAI_STORAGE_RESTORE_VERIFIED':'yes','LIBRAAI_PRODUCTION_ACCEPTANCE_PASSED':'yes',
          'LIBRAAI_ENV':'production','SSLCOMMERZ_SANDBOX':'false','BKASH_SANDBOX':'false'
        }
        report = build_public_notices(env)
        self.assertEqual({item['id'] for item in report['items']}, {'creator-payouts'})
        self.assertEqual(report['open_count'], 1)
        self.assertFalse(report['launch_ready'])
        self.assertIn('not independent proof', report['scope'])

    def test_semantic_provider_is_optional_not_a_blocker(self):
        report = build_readiness({})
        semantic = next(x for x in report['items'] if x['id'] == 'semantic-ai')
        self.assertEqual(semantic['status'], 'optional')
        self.assertIn('local', semantic['summary'])

    def test_rights_and_security_are_explicit_gates(self):
        report = build_readiness({})
        items = {x['id']: x for x in report['items']}
        self.assertEqual(items['content-rights']['status'], 'blocked')
        self.assertEqual(items['security-review']['status'], 'blocked')

if __name__ == '__main__': unittest.main()
