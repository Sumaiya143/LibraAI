import ast, pathlib, unittest
ROOT=pathlib.Path(__file__).parent
class PlatformTests(unittest.TestCase):
 def test_valid_python(self):
  for f in ('app.py','platform_plus.py','extended.py','research_tools.py','learning_engine.py'):
   ast.parse((ROOT/f).read_text())
 def test_no_duplicate_health(self):
  self.assertNotIn("@plus.get('/api/health')",(ROOT/'platform_plus.py').read_text())
 def test_visual_theme_exists(self):
  css=(ROOT/'premium_ui.css').read_text()
  self.assertIn('@media(max-width:520px)',css)
  self.assertIn('body.light-ui',css)
 def test_export_is_authenticated(self):
  s=(ROOT/'platform_plus.py').read_text()
  self.assertIn('def export_data():\n    u=require()',s)
