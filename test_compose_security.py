import unittest
from pathlib import Path
ROOT=Path(__file__).parent
class ComposeSecurityTests(unittest.TestCase):
    def test_bound_to_loopback(self):
        self.assertIn('127.0.0.1:8000:8000', (ROOT/'compose.yaml').read_text())
    def test_drops_linux_capabilities(self):
        data=(ROOT/'compose.yaml').read_text()
        for item in ('no-new-privileges:true','cap_drop:', 'read_only: true','libraai_data:/data'):
            self.assertIn(item,data)
    def test_secrets_excluded_from_build_context(self):
        data=(ROOT/'.dockerignore').read_text().splitlines()
        self.assertIn('.env',data)
        self.assertIn('*.db',data)
    def test_env_example_is_fail_closed(self):
        data=(ROOT/'.env.example').read_text()
        for item in ('LIBRAAI_LIVE_PAYMENT_E2E_VERIFIED=no','LIBRAAI_LICENSE_RIGHTS_VERIFIED=no','LIBRAAI_SECURITY_REVIEW_PASSED=no'):
            self.assertIn(item,data)
if __name__=='__main__': unittest.main()
