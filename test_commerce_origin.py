import unittest
from unittest.mock import Mock,patch
from commerce_server import Commerce,commerce_origin_allowed

class CommerceOriginTests(unittest.TestCase):
 def test_same_origin(self):
  self.assertTrue(commerce_origin_allowed('https://books.example','books.example'))
  self.assertTrue(commerce_origin_allowed('http://localhost:8000','localhost:8000'))
 def test_cross_origin(self):
  for origin in ['https://evil.example','null','https://books.example.evil',
                 'https://books.example@evil.example','ftp://books.example',
                 'https://books.example/path','https://books.example?x=1']:
   with self.subTest(origin=origin):self.assertFalse(commerce_origin_allowed(origin,'books.example'))
 def test_missing_origin_server_client(self):
  self.assertTrue(commerce_origin_allowed(None,'books.example'))
 def test_blocked_before_any_payout_processing(self):
  handler=object.__new__(Commerce)
  handler.headers={'Origin':'https://evil.example','Host':'books.example'}
  handler.path='/api/admin/payout/review'
  handler.send=Mock()
  with patch.object(Commerce,'user',side_effect=AssertionError('Must not read user')):
   handler.do_POST()
  handler.send.assert_called_once_with(403,{'error':'Cross-origin request rejected'})
 def test_blocked_before_bkash_start(self):
  handler=object.__new__(Commerce)
  handler.headers={'Origin':'null','Host':'books.example'}
  handler.path='/api/commerce/bkash/start'
  handler.send=Mock()
  handler.do_POST()
  handler.send.assert_called_once_with(403,{'error':'Cross-origin request rejected'})

if __name__=='__main__':unittest.main()
