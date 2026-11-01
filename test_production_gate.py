import tempfile
import unittest
from pathlib import Path
from production_gate import release_gate, REQUIRED_FILES
from test_gateway_readiness import GOOD


class ProductionGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for filename in REQUIRED_FILES:
            (self.root / filename).write_text('test', encoding='utf-8')

    def test_complete_offline_release_review(self):
        self.assertTrue(release_gate(self.root, GOOD)['ready_for_release_review'])

    def test_rejects_missing_source_file(self):
        (self.root / 'payment_routes.py').unlink()
        self.assertFalse(release_gate(self.root, GOOD)['ready_for_release_review'])

    def test_rejects_customer_database_in_nested_folder(self):
        (self.root / 'backup').mkdir()
        (self.root / 'backup' / 'customers.sqlite3').write_bytes(b'fake')
        result = release_gate(self.root, GOOD)
        self.assertFalse(result['ready_for_release_review'])
        self.assertIn('backup/customers.sqlite3', result['prohibited_package_files'])

    def test_rejects_secrets_and_private_keys(self):
        (self.root / '.env.production').write_text('SECRET_KEY=private')
        (self.root / 'cert.pem').write_text('private')
        result = release_gate(self.root, GOOD)
        self.assertFalse(result['ready_for_release_review'])
        self.assertIn('.env.production', result['prohibited_package_files'])

    def test_fails_closed_on_missing_merchant_config(self):
        self.assertFalse(release_gate(self.root, {})['ready_for_release_review'])


    def test_rejects_nested_environment_secrets(self):
        (self.root / 'deploy').mkdir()
        (self.root / 'deploy' / '.env.staging').write_text('PASSWORD=secret')
        result = release_gate(self.root, GOOD)
        self.assertFalse(result['ready_for_release_review'])
        self.assertIn('deploy/.env.staging', result['prohibited_package_files'])

    def test_rejects_symlinked_required_file(self):
        source = self.root / 'app.py'
        source.unlink()
        target = self.root / 'source.txt'
        target.write_text('source')
        try:
            source.symlink_to(target)
        except OSError:
            self.skipTest('Symlinks not supported on this platform')
        result = release_gate(self.root, GOOD)
        self.assertFalse(result['ready_for_release_review'])
        self.assertIn('app.py', result['prohibited_package_files'])

    def test_rejects_development_artifacts(self):
        cache = self.root / '__pycache__'
        cache.mkdir()
        (cache / 'app.pyc').write_bytes(b'test')
        result = release_gate(self.root, GOOD)
        self.assertFalse(result['ready_for_release_review'])
        self.assertTrue(any('__pycache__' in x for x in result['prohibited_package_files']))

    def test_rejects_linked_directory(self):
        external = tempfile.TemporaryDirectory()
        self.addCleanup(external.cleanup)
        try:
            (self.root / 'linked').symlink_to(external.name, target_is_directory=True)
        except OSError:
            self.skipTest('Symlinks not supported on this platform')
        result = release_gate(self.root, GOOD)
        self.assertFalse(result['ready_for_release_review'])
        self.assertIn('linked', result['prohibited_package_files'])

    def test_does_not_expose_credential_values(self):
        env = {**GOOD, 'BKASH_APP_SECRET': 'NEVER_PRINT_THIS_SECRET'}
        self.assertNotIn('NEVER_PRINT_THIS_SECRET', str(release_gate(self.root, env)))
