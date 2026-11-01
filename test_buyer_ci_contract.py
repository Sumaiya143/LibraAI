import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

class BuyerCIContract(unittest.TestCase):
    def test_ci_file_exists(self):
        self.assertTrue((ROOT/'.github/workflows/buyer-verification.yml').is_file())

    def test_ci_runs_all_three_acceptance_steps(self):
        text=(ROOT/'.github/workflows/buyer-verification.yml').read_text()
        for cmd in ('python -B buyer_preflight.py', 'python -B verify_full_test_suite.py', 'python -B buyer_acceptance.py'):
            self.assertIn(cmd,text)

    def test_ci_enforces_zero_skips(self):
        runner = (ROOT/'verify_full_test_suite.py').read_text()
        self.assertIn('if result.skipped', runner)
        self.assertIn('return 1', runner)

    def test_ci_read_only_permissions(self):
        text=(ROOT/'.github/workflows/buyer-verification.yml').read_text()
        self.assertIn('contents: read',text)
        self.assertNotIn('pull_request_target:',text)

    def test_ci_does_not_claim_live_payments(self):
        text=(ROOT/'BUYER_VERIFICATION_CI_BN.md').read_text()
        self.assertIn('CI green মানে live-market certification নয়',text)
