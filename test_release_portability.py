"""Dependency-free checks for local/GitHub release bootstrap reliability."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent


class ReleasePortabilityTests(unittest.TestCase):
    def test_github_frontend_job_does_not_cache_missing_lockfile(self):
        workflow = (ROOT / '.github/workflows/full-release-verification.yml').read_text(encoding='utf-8')
        self.assertIn("node-version: '20'", workflow)
        self.assertNotIn('cache-dependency-path: frontend/package-lock.json', workflow)

    def test_frontend_bootstrap_generates_lockfile_before_npm_ci(self):
        script = (ROOT / 'START_FRONTEND.bat').read_text(encoding='utf-8').lower()
        self.assertIn('npm install --package-lock-only', script)
        self.assertIn('npm ci', script)
        self.assertLess(script.index('npm install --package-lock-only'), script.index('npm ci'))

    def test_required_backend_and_frontend_entrypoints_exist(self):
        for rel in ('app.py', 'requirements.txt', 'frontend/package.json', 'START_BACKEND.bat', 'START_FRONTEND.bat', 'RUN_TESTS.bat'):
            with self.subTest(path=rel):
                self.assertTrue((ROOT / rel).exists(), rel)

    def test_no_real_environment_file_is_packaged(self):
        for rel in ('.env', '.env.local', '.env.production'):
            with self.subTest(path=rel):
                self.assertFalse((ROOT / rel).exists(), rel)


if __name__ == '__main__':
    unittest.main(verbosity=2)
