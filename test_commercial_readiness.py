import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from commercial_readiness import inspect

class ReadinessTests(unittest.TestCase):
    def test_empty_env_fails_closed(self):
        r=inspect({})
        self.assertFalse(r['ready'])
        self.assertGreater(len(r['issues']),5)
    def test_credentials_not_exposed(self):
        r=inspect({'SSLCOMMERZ_STORE_PASSWORD':'my-private-password'})
        self.assertNotIn('my-private-password',repr(r))
    def test_usd_storefront_is_blocker(self):
        with TemporaryDirectory() as d:
            Path(d,'app.py').write_text('Bookstore & marketplace <p>${{b[ Sandbox checkout')
            r=inspect({},d)
            self.assertTrue(any('USD' in x for x in r['issues']))
    def test_no_false_ready_on_complete_secrets(self):
        env={'LIBRAAI_ENV':'production','SECRET_KEY':'a'*48,'LIBRAAI_PUBLIC_URL':'https://example.com'}
        for k in ('SSLCOMMERZ_STORE_ID','SSLCOMMERZ_STORE_PASSWORD','BKASH_APP_KEY','BKASH_APP_SECRET','BKASH_USERNAME','BKASH_PASSWORD'):
            env[k]='valid-value'
        self.assertFalse(inspect(env)['ready'])

if __name__=='__main__': unittest.main()
