import unittest
from catalog_server import auth_throttled, _AUTH_ATTEMPTS
class AuthThrottleTests(unittest.TestCase):
 def setUp(self): _AUTH_ATTEMPTS.clear()
 def test_blocks_eleventh_attempt(self):
  for i in range(10): self.assertFalse(auth_throttled('client','/api/login',now=100+i))
  self.assertTrue(auth_throttled('client','/api/login',now=110))
 def test_separate_routes(self):
  for i in range(10): auth_throttled('client','/api/login',now=100+i)
  self.assertFalse(auth_throttled('client','/api/signup',now=110))
 def test_window_expires(self):
  for i in range(10): auth_throttled('client','/api/login',now=100+i)
  self.assertFalse(auth_throttled('client','/api/login',now=1010))
