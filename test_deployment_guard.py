import unittest
from deployment_guard import is_production,require_development_server

class DeploymentGuardTests(unittest.TestCase):
 def test_development_allowed(self):
  for value in ('', 'development', 'test'):
   self.assertTrue(require_development_server({'LIBRA_ENV':value}))
 def test_production_refused(self):
  for value in ('production','PROD',' live '):
   with self.subTest(value=value), self.assertRaisesRegex(RuntimeError,'Refusing to run'):
    require_development_server({'LIBRA_ENV':value})
 def test_detection(self):
  self.assertTrue(is_production({'LIBRA_ENV':'Production'}))
  self.assertFalse(is_production({'LIBRA_ENV':'staging'}))
