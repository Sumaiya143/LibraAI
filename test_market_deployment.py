import unittest
from pathlib import Path
from market_preflight import check_config

class MarketDeploymentTests(unittest.TestCase):
    def test_no_public_app_port(self):
        text = Path('compose.market.yaml').read_text()
        app = text.split('  caddy:')[0]
        self.assertNotIn('ports:', app)
        self.assertIn('expose:', app)

    def test_https_proxy(self):
        text = Path('Caddyfile').read_text()
        self.assertIn('{$LIBRAAI_DOMAIN}', text)
        self.assertIn('reverse_proxy libraai:8000', text)

    def test_preflight_rejects_defaults(self):
        self.assertTrue(check_config({}))

    def test_preflight_rejects_url_mismatch(self):
        self.assertTrue(any('PUBLIC_URL' in issue for issue in check_config({'LIBRAAI_DOMAIN':'books.example.com','LIBRAAI_PUBLIC_URL':'https://other.example.com'})))

    def test_flags_fail_closed(self):
        issues = check_config({'LIBRAAI_DOMAIN':'books.example.com','LIBRAAI_PUBLIC_URL':'https://books.example.com'})
        self.assertEqual(sum('Not verified:' in issue for issue in issues), 3)
