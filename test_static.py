"""Dependency-free source-level checks; NOT end-to-end Flask tests."""
import ast, pathlib, unittest
ROOT=pathlib.Path(__file__).parent
class SourceChecks(unittest.TestCase):
    def test_python_parses(self):
        for name in ('app.py','extended.py','research_tools.py'):
            with self.subTest(name=name): ast.parse((ROOT/name).read_text(encoding='utf8'))
    def test_api_routes_present(self):
        source=(ROOT/'app.py').read_text()
        for route in ('/api/books','/api/ai','/api/health'):
            with self.subTest(route=route): self.assertIn(route,source)
    def test_password_hashing_present(self):
        source=(ROOT/'app.py').read_text()
        self.assertIn('generate_password_hash',source)
        self.assertIn('check_password_hash',source)
    def test_csrf_check_present(self):
        self.assertIn('verify_form_csrf', (ROOT/'app.py').read_text())
if __name__=='__main__': unittest.main(verbosity=2)
