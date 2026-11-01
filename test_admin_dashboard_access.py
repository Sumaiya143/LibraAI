"""Regression tests for server-side admin dashboard authorization."""
import unittest
from unittest.mock import patch
from commerce_server import Commerce

class AdminDashboardAccessTests(unittest.TestCase):
 def request(self, path, role):
  handler=object.__new__(Commerce)
  handler.path=path
  replies=[]
  user=None if role is None else {'id':1,'role':role}
  with patch.object(Commerce,'user',return_value=user), patch.object(Commerce,'send',side_effect=lambda *args: replies.append(('send',args))), patch.object(Commerce,'redirect',side_effect=lambda *args: replies.append(('redirect',args))):
   if role=='admin' and path=='/admin-commerce.html':
    # Avoid invoking HTTP filesystem methods; verify delegation to parent.
    with patch('production.Production.do_GET',autospec=True) as delegate:
     handler.do_GET()
     self.assertEqual(delegate.call_count,1)
   else:
    handler.do_GET()
  return replies
 def test_anonymous_denied(self):
  self.assertEqual(self.request('/admin-commerce.html',None)[0][1][0],401)
 def test_customer_denied(self):
  self.assertEqual(self.request('/admin-commerce.html','customer')[0][1][0],403)
 def test_merchant_denied(self):
  self.assertEqual(self.request('/admin-commerce.html','merchant')[0][1][0],403)
 def test_admin_alias_redirect(self):
  self.assertEqual(self.request('/admin-commerce','admin'),[('redirect',('/admin-commerce.html',))])
 def test_query_cannot_bypass_gate(self):
  self.assertEqual(self.request('/admin-commerce.html?x=1',None)[0][1][0],401)

if __name__=='__main__':unittest.main()
