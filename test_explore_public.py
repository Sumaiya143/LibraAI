import unittest
from pathlib import Path
P=Path(__file__).parent
class ExplorePublicTests(unittest.TestCase):
 def test_route_wired(self):
  s=(P/'app.py').read_text(); self.assertIn("@app.get('/explore')",s);self.assertIn("@app.get('/assets/explore.js')",s)
 def test_catalog_uses_real_api(self):
  s=(P/'explore.js').read_text();self.assertIn("fetch('/api/books",s);self.assertIn('URLSearchParams',s)
 def test_no_unsafe_html_in_catalog_renderer(self):
  s=(P/'explore.js').read_text();self.assertNotIn('innerHTML',s);self.assertIn('textContent',s)
 def test_accessible_controls(self):
  s=(P/'explore.html').read_text();self.assertIn('aria-live',s);self.assertIn('role="search"',s)
if __name__=='__main__':unittest.main()
