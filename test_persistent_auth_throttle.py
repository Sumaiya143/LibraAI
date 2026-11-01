import os, tempfile, unittest
from catalog_server import persistent_auth_throttled

class PersistentAuthThrottleTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.database=os.path.join(self.tmp.name,'throttle.sqlite')
 def tearDown(self): self.tmp.cleanup()
 def test_limit_persists_between_connections(self):
  for i in range(10):
   self.assertFalse(persistent_auth_throttled('192.0.2.10','/api/login',now=100+i,database=self.database))
  self.assertTrue(persistent_auth_throttled('192.0.2.10','/api/login',now=110,database=self.database))
 def test_route_and_client_isolation(self):
  for i in range(10): persistent_auth_throttled('a','/api/login',now=100+i,database=self.database)
  self.assertFalse(persistent_auth_throttled('b','/api/login',now=110,database=self.database))
  self.assertFalse(persistent_auth_throttled('a','/api/signup',now=110,database=self.database))
 def test_window_expiration(self):
  for i in range(10): persistent_auth_throttled('a','/api/login',now=100+i,database=self.database)
  self.assertFalse(persistent_auth_throttled('a','/api/login',now=1010,database=self.database))
 def test_invalid_route(self):
  with self.assertRaises(ValueError):persistent_auth_throttled('a','/api/orders',database=self.database)
