"""Static dashboard safety and wiring checks."""
import unittest
from pathlib import Path
ROOT=Path(__file__).parent/'static'
class AdminCommerceDashboardTests(unittest.TestCase):
 def test_dashboard_has_no_embedded_secrets(self):
  html=(ROOT/'admin-commerce.html').read_text()
  self.assertIn('admin-commerce.js',html)
  self.assertNotIn('SSLCZ_STORE_PASSWORD',html)
  self.assertNotIn('BKASH_APP_SECRET',html)
 def test_dashboard_uses_existing_admin_only_endpoint(self):
  js=(ROOT/'admin-commerce.js').read_text()
  self.assertIn('/api/admin/commerce/health',js)
  self.assertIn('response.status === 401',js)
  self.assertIn('response.status === 403',js)
 def test_diagnostic_text_uses_safe_dom_methods(self):
  js=(ROOT/'admin-commerce.js').read_text()
  self.assertNotIn('innerHTML',js)
  self.assertIn('textContent',js)
  self.assertIn('replaceChildren',js)
 def test_dashboard_does_not_modify_commerce_data(self):
  js=(ROOT/'admin-commerce.js').read_text()
  self.assertNotIn("method:'POST'",js)
  self.assertNotIn("method:'DELETE'",js)
if __name__=='__main__':unittest.main()
