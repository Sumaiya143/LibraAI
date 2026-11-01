import tempfile,unittest
from pathlib import Path
from buyer_preflight import inspect_package,REQUIRED

class BuyerPreflightTests(unittest.TestCase):
    def test_complete_structure(self):
        with tempfile.TemporaryDirectory() as t:
            for name in REQUIRED:
                (Path(t)/name).touch()
            self.assertEqual(inspect_package(t),[])
    def test_missing_module(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertTrue(any('Missing' in e for e in inspect_package(t)))
    def test_blocks_customer_database(self):
        with tempfile.TemporaryDirectory() as t:
            for name in REQUIRED: (Path(t)/name).touch()
            (Path(t)/'customers.db').touch()
            self.assertTrue(any('customer database' in e for e in inspect_package(t)))
    def test_blocks_secret_file(self):
        with tempfile.TemporaryDirectory() as t:
            for name in REQUIRED: (Path(t)/name).touch()
            (Path(t)/'.env').touch()
            self.assertTrue(any('secret' in e for e in inspect_package(t)))
    def test_blocks_private_key(self):
        with tempfile.TemporaryDirectory() as t:
            for name in REQUIRED: (Path(t)/name).touch()
            (Path(t)/'cert.pem').touch()
            self.assertTrue(inspect_package(t))

if __name__=='__main__': unittest.main()
