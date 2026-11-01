# Disable request throttling in high-volume integration tests only.
import os
os.environ.setdefault('LIBRAAI_AUTH_THROTTLE','0')
import unittest
from test_reading_goals import GoalTests
class PrivacyExportTests(GoalTests):
 def test_export_requires_authentication(self):
  self.assertEqual(self.req('/api/privacy/export')[0],401)
 def test_export_includes_only_own_profile(self):
  self.login()
  self.req('/api/reading-goals',{'weekly_books':4})
  status,data=self.req('/api/privacy/export')
  self.assertEqual(status,200)
  self.assertEqual(data['profile']['role'],'customer')
  self.assertEqual(len(data['data']['reading_goals']),1)
  self.assertEqual(data['data']['reading_goals'][0]['weekly_books'],4)
  self.assertNotIn('hash',data['profile'])
if __name__=='__main__':unittest.main()
