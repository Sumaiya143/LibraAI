import tempfile
import unittest
from pathlib import Path
from buyer_preflight import inspect_package, REQUIRED

class BuyerPreflightHardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in REQUIRED:
            (self.root / name).write_text('placeholder')

    def test_clean_package(self):
        self.assertEqual(inspect_package(self.root), [])

    def test_nested_secrets_and_databases_blocked(self):
        folder = self.root / 'nested'
        folder.mkdir()
        (folder / 'credentials.json').write_text('{}')
        (folder / 'customer.sqlite3').write_bytes(b'')
        self.assertEqual(len(inspect_package(self.root)), 2)

    def test_development_cache_blocked(self):
        folder = self.root / '.pytest_cache'
        folder.mkdir()
        (folder / 'state').write_text('x')
        self.assertTrue(any('Development artifact' in x for x in inspect_package(self.root)))

    def test_symlink_blocked(self):
        link = self.root / 'shortcut'
        try:
            link.symlink_to(self.root / 'app.py')
        except (OSError, NotImplementedError):
            self.skipTest('Symlink unsupported')
        self.assertTrue(any('Symbolic link' in x for x in inspect_package(self.root)))

if __name__ == '__main__':
    unittest.main()
