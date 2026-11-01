import unittest
from pathlib import Path
ROOT=Path(__file__).parent/'static'
class AccountSecurityUI(unittest.TestCase):
 def test_security_page_forms(self):
  html=(ROOT/'account-security.html').read_text()
  for marker in ('password-form','logout-form','current-password','new-password','verify-password','autocomplete="new-password"'):self.assertIn(marker,html)
 def test_correct_security_endpoints(self):
  js=(ROOT/'account-security.js').read_text()
  self.assertIn('/api/security/change-password',js)
  self.assertIn('/api/security/logout-all',js)
  self.assertIn("credentials:'same-origin'",js)
 def test_passwords_not_persisted_in_browser(self):
  js=(ROOT/'account-security.js').read_text()
  for forbidden in ('localStorage','sessionStorage','document.cookie','innerHTML'):self.assertNotIn(forbidden,js)
 def test_success_redirects_to_signin(self):
  js=(ROOT/'account-security.js').read_text()
  self.assertIn("window.location.assign('/account.html')",js)
  self.assertIn('form.reset()',js)
if __name__=='__main__':unittest.main()
