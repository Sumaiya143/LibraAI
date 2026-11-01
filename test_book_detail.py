import unittest
from pathlib import Path
P=Path(__file__).resolve().parent
class BookDetailTests(unittest.TestCase):
 def test_api_route_exists(self):
  s=(P/'app.py').read_text();self.assertIn("@app.get('/api/books/<int:book_id>')",s);self.assertIn('WHERE id=?',s)
 def test_page_route_exists(self):
  self.assertIn("@app.get('/books/<int:book_id>')",(P/'app.py').read_text())
 def test_escapes_dynamic_text(self):
  s=(P/'book_detail.js').read_text();self.assertIn('.textContent=value',s);self.assertNotIn('.innerHTML',s)
 def test_accessible_details(self):
  s=(P/'book_detail.html').read_text();self.assertIn('aria-live="polite"',s);self.assertIn('aria-pressed="false"',s)
 def test_navigation(self):
  self.assertIn("link.href='/books/'",(P/'explore.js').read_text())
if __name__=='__main__':unittest.main()
