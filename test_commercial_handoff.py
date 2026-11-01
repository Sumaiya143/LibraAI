# Disable request throttling in high-volume integration tests only.
import os
os.environ.setdefault('LIBRAAI_AUTH_THROTTLE','0')
import unittest
from catalog_server import CatalogHandler
from pathlib import Path
class HandoffTests(unittest.TestCase):
 def test_health_routes_declared(self):
  source=Path(__file__).with_name('catalog_server.py').read_text()
  self.assertIn('/api/health/live',source)
  self.assertIn('/api/health/ready',source)
 def test_preflight_fail_closed(self):
  source=Path(__file__).with_name('production_preflight.py').read_text()
  self.assertIn('Persistent session storage',source)
  self.assertIn('False',source)
if __name__=='__main__':unittest.main()
