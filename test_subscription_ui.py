import unittest
from pathlib import Path
ROOT=Path(__file__).parent/'static'
class SubscriptionUI(unittest.TestCase):
 def test_page_contains_invoice_management(self):
  html=(ROOT/'subscriptions.html').read_text()
  self.assertIn('Subscription invoices',html)
  self.assertIn('data-plan="student"',html)
  self.assertIn('data-plan="premium"',html)
 def test_script_uses_authenticated_endpoints(self):
  js=(ROOT/'subscriptions.js').read_text()
  self.assertIn('credentials:\'same-origin\'',js)
  for path in ('/api/commerce/invoices','/api/commerce/subscription/invoice','/api/commerce/subscription/cancel-invoice'):self.assertIn(path,js)
 def test_no_unsafe_invoice_html_injection(self):
  js=(ROOT/'subscriptions.js').read_text()
  self.assertNotIn('innerHTML',js)
  self.assertIn('textContent',js)
 def test_invoice_does_not_claim_payment(self):
  html=(ROOT/'subscriptions.html').read_text()
  self.assertIn('Payments and recurring charges are not activated',html)
if __name__=='__main__':unittest.main()
