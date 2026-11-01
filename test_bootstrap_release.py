"""Static integration guards for the release bootstrap path."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent

class BootstrapRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'app.py').read_text()
        cls.tree = ast.parse(cls.source)

    def test_server_starts_after_all_blueprints(self):
        entry = [n for n in self.tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == "__name__ == '__main__'"]
        self.assertEqual(len(entry), 1)
        self.assertIs(entry[0], self.tree.body[-1])
        self.assertIn('app.register_blueprint(waitlist_bp)', self.source[:entry[0].lineno * 1000])

    def test_all_python_files_compile(self):
        for file in ROOT.glob('*.py'):
            with self.subTest(file=file.name):
                compile(file.read_bytes(), str(file), 'exec')

    def test_production_requires_secret(self):
        self.assertIn("len(os.environ.get('SECRET_KEY', '')) < 32", self.source)

    def test_post_requests_require_csrf(self):
        self.assertIn('def verify_form_csrf()', self.source)
        self.assertIn('hmac.compare_digest(token,supplied)', self.source)

    def test_rights_aware_reader_registered(self):
        self.assertIn('app.register_blueprint(reader_plus)', self.source)
        self.assertIn('app.register_blueprint(licensed)', self.source)

if __name__ == '__main__': unittest.main()
