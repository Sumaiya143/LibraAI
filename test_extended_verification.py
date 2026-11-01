import json, os, subprocess, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent

class ExtendedVerificationTests(unittest.TestCase):
    def test_external_preflight_is_non_destructive_without_credentials(self):
        env = os.environ.copy()
        for key in ('LIBRAAI_LLM_API_KEY','OPENAI_API_KEY','SSLCZ_STORE_ID','SSLCZ_STORE_PASSWORD','BKASH_USERNAME','BKASH_PASSWORD','BKASH_APP_KEY','BKASH_APP_SECRET','RUN_OPENAI_LIVE_TEST'):
            env.pop(key, None)
        result = subprocess.run([sys.executable, '-B', str(ROOT/'external_integration_preflight.py')], env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data['ai']['configured'])
        self.assertFalse(data['payments']['live_payment_attempted'])

    def test_security_review_declares_scope_limit(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT/'security_review.py')], capture_output=True, text=True, timeout=120)
        data = json.loads(result.stdout)
        self.assertIn('not a penetration test', data['scope_note'].lower())
        self.assertGreater(data['files_scanned'], 0)
