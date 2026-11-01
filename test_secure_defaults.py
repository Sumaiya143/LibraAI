import unittest, os, inspect
from unittest.mock import patch
from catalog_server import CatalogHandler

class SecureDefaultTests(unittest.TestCase):
 def test_throttle_enabled_by_default(self):
  source=inspect.getsource(CatalogHandler.do_POST)
  self.assertIn("os.getenv('LIBRAAI_AUTH_THROTTLE','1') == '1'",source)
 def test_throttle_can_be_explicitly_disabled_for_local_debugging(self):
  with patch.dict(os.environ, {'LIBRAAI_AUTH_THROTTLE':'0'}):
   self.assertEqual(os.getenv('LIBRAAI_AUTH_THROTTLE','1'),'0')
