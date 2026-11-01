# Disable request throttling in high-volume integration tests only.
import os
os.environ.setdefault('LIBRAAI_AUTH_THROTTLE','0')
import unittest
from test_reading_goals import GoalTests
class PrivacyControlsTests(GoalTests):
 def test_clear_requires_auth(self):
  self.assertEqual(self.req('/api/privacy/clear-reading-data',{'confirmation':'DELETE MY READING DATA'})[0],401)
 def test_clear_requires_exact_confirmation(self):
  self.login();self.req('/api/reading-goals',{'weekly_books':5})
  self.assertEqual(self.req('/api/privacy/clear-reading-data',{'confirmation':'delete'})[0],400)
  self.assertEqual(self.req('/api/reading-goals')[1]['weekly_books'],5)
 def test_clear_only_own_reading_data(self):
  self.login();self.req('/api/reading-goals',{'weekly_books':5})
  first=self.opener
  self.opener=__import__('urllib.request',fromlist=['build_opener']).build_opener(__import__('urllib.request',fromlist=['HTTPCookieProcessor']).HTTPCookieProcessor(__import__('http.cookiejar',fromlist=['CookieJar']).CookieJar()))
  self.login();self.req('/api/reading-goals',{'weekly_books':9})
  self.assertEqual(self.req('/api/privacy/clear-reading-data',{'confirmation':'DELETE MY READING DATA'})[0],200)
  self.assertIsNone(self.req('/api/reading-goals')[1]['weekly_books'])
  self.opener=first
  self.assertEqual(self.req('/api/reading-goals')[1]['weekly_books'],5)
if __name__=='__main__':unittest.main()
