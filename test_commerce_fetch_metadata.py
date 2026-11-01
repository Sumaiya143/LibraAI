import unittest
from unittest.mock import Mock, patch
from commerce_server import Commerce, commerce_browser_write_allowed

class FetchMetadataTests(unittest.TestCase):
 def test_reject_cross_site_without_origin(self):
  self.assertFalse(commerce_browser_write_allowed({'Host':'books.example','Sec-Fetch-Site':'cross-site'}))
 def test_reject_same_site_sibling_origin(self):
  self.assertFalse(commerce_browser_write_allowed({'Host':'books.example','Sec-Fetch-Site':'same-site'}))
 def test_allow_same_origin(self):
  self.assertTrue(commerce_browser_write_allowed({'Host':'books.example','Origin':'https://books.example','Sec-Fetch-Site':'same-origin'}))
 def test_origin_still_checked(self):
  self.assertFalse(commerce_browser_write_allowed({'Host':'books.example','Origin':'https://attacker.example','Sec-Fetch-Site':'same-origin'}))
 def test_allow_webhook_without_browser_headers(self):
  self.assertTrue(commerce_browser_write_allowed({'Host':'books.example'}))
 def test_cross_site_blocked_before_user_or_db(self):
  handler=object.__new__(Commerce)
  handler.headers={'Host':'books.example','Sec-Fetch-Site':'cross-site'}
  handler.path='/api/commerce/subscription/invoice'
  handler.send=Mock()
  with patch.object(Commerce,'user',side_effect=AssertionError('user() must not run')):
   handler.do_POST()
  handler.send.assert_called_once_with(403,{'error':'Cross-origin request rejected'})

if __name__=='__main__': unittest.main()
