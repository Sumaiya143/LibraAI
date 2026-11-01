import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
class ReleaseAccessibilityTests(unittest.TestCase):
 def test_skip_navigation(self):
  source=(ROOT/'app.py').read_text()
  self.assertIn('href="#main-content"',source)
  self.assertIn('id="main-content"',source)
 def test_light_default(self):
  self.assertIn("let mode='light'",(ROOT/'app.py').read_text())
 def test_navigation_landmark(self):
  self.assertIn('aria-label="Main navigation"',(ROOT/'app.py').read_text())
 def test_responsive_and_focus(self):
  css=(ROOT/'premium_ui.css').read_text()
  self.assertIn('.skip-link:focus',css)
  self.assertIn('max-width:900px',css)
 def test_no_production_demo_password(self):
  source=(ROOT/'app.py').read_text()
  self.assertIn("os.environ.get('LIBRAAI_ENV') != 'production'",source)
if __name__=='__main__': unittest.main()
