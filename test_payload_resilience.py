"""Regression tests for malformed client payload handling."""
import io, unittest
from unittest.mock import patch
from server import Handler
from production import Production

class RequestBodyTests(unittest.TestCase):
 def parse(self, raw, length=None):
  h=object.__new__(Handler)
  h.headers={'Content-Length':str(len(raw) if length is None else length)}
  h.rfile=io.BytesIO(raw)
  return h.body()
 def test_rejects_list_json(self):
  self.assertEqual(self.parse(b'[1,2,3]'),{})
 def test_rejects_scalar_json(self):
  self.assertEqual(self.parse(b'42'),{})
 def test_rejects_null_json(self):
  self.assertEqual(self.parse(b'null'),{})
 def test_accepts_object_json(self):
  self.assertEqual(self.parse(b'{"name":"reader"}'),{'name':'reader'})
 def test_rejects_malformed_json(self):
  self.assertEqual(self.parse(b'{oops'),{})
 def test_rejects_negative_length(self):
  self.assertEqual(self.parse(b'{}',-1),{})
 def test_rejects_oversized_length(self):
  self.assertEqual(self.parse(b'{}',100001),{})
 def test_ipn_rejects_non_numeric_content_length(self):
  h=object.__new__(Production)
  h.path='/api/payments/ipn'
  h.headers={'Content-Length':'not-a-number'}
  h.send=lambda status, obj:(status,obj)
  status,body=h.do_POST()
  self.assertEqual(status,400)
  self.assertIn('payload',body['error'])

if __name__=='__main__':unittest.main()
