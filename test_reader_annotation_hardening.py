"""Regression checks for reader missing-resource and annotation input validation."""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parent
SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)

class ReaderAnnotationHardeningTests(unittest.TestCase):
    def test_reader_checks_missing_book_before_rendering_sample(self):
        start = SOURCE.index("@app.route('/reader/<int:bid>'")
        end = SOURCE.index("@app.post('/annotation/<int:bid>')", start)
        route = SOURCE[start:end]
        self.assertIn('if not b:', route)
        self.assertIn('abort(404)', route)
        self.assertLess(route.index('abort(404)'), route.index("sample=(f\"{b['title']}"))

    def test_annotation_uses_allowlists_and_bounds(self):
        start = SOURCE.index("@app.post('/annotation/<int:bid>')")
        end = SOURCE.index("@app.post('/progress/<int:bid>')", start)
        route = SOURCE[start:end]
        for expected in ('Unsupported annotation type.', 'Unsupported annotation color.',
                         'len(content) > 4000', '1 <= page_number <= 1000000',
                         "SELECT 1 FROM books WHERE id=?", 'finally:', 'c.close()'):
            self.assertIn(expected, route)

    def test_annotation_does_not_use_unchecked_form_key_access(self):
        start = SOURCE.index("@app.post('/annotation/<int:bid>')")
        end = SOURCE.index("@app.post('/progress/<int:bid>')", start)
        route = SOURCE[start:end]
        self.assertNotIn("request.form['kind']", route)
        self.assertNotIn("request.form['content']", route)
        self.assertNotIn("request.form['page']", route)

    def test_python_source_parses(self):
        ast.parse(SOURCE)

if __name__ == '__main__':
    unittest.main()
