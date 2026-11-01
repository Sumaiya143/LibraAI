"""Static checks of fail-closed production deployment orchestration."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parent

class MarketGoLiveTests(unittest.TestCase):
    def setUp(self):
        self.script = (ROOT / 'market_go_live.sh').read_text()

    def test_preflight_before_build_and_up(self):
        self.assertLess(self.script.index('market_preflight.py'), self.script.index(' build libraai'))
        self.assertLess(self.script.index('config --quiet'), self.script.index(' up -d'))

    def test_no_embedded_credentials(self):
        self.assertNotIn('SECRET_KEY=', self.script)
        self.assertNotIn('SSLCOMMERZ_STORE_PASSWORD=', self.script)

    def test_secret_file_permission_guard(self):
        self.assertIn('chmod 600 .env', self.script)
        self.assertIn('stat -c', self.script)

    def test_fail_closed_shell(self):
        self.assertIn('set -Eeuo pipefail', self.script)
        self.assertIn('market_preflight.py --env .env', self.script)

if __name__ == '__main__':
    unittest.main()
