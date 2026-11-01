# Disable request throttling in high-volume integration tests only.
import os
os.environ.setdefault('LIBRAAI_AUTH_THROTTLE','0')
import unittest
from test_reading_goals import GoalTests

class InputHardeningTests(GoalTests):
 def test_rejects_malformed_goals(self):
  self.login()
  for value in (True, 2.5, '2.5', [], {}, None):
   self.assertEqual(self.req('/api/reading-goals',{'weekly_books':value})[0],400)
 def test_rejects_non_object_body(self):
  self.login()
  self.assertEqual(self.req('/api/reading-goals',[])[0],400)
  self.assertEqual(self.req('/api/wishlist',[])[0],400)
 def test_rejects_non_boolean_wishlist_flag(self):
  self.login()
  self.assertEqual(self.req('/api/wishlist',{'book_id':1,'saved':'false'})[0],400)
 def test_rejects_fractional_or_boolean_progress(self):
  self.login()
  for value in (True,2.5,'50.5',[],None):
   self.assertEqual(self.req('/api/reading-progress',{'book_id':1,'percent':value})[0],400)
 def test_rejects_invalid_book_ids(self):
  self.login()
  for value in (True,1.5,'1.5',-1,None):
   self.assertEqual(self.req('/api/wishlist',{'book_id':value})[0],400)

if __name__=='__main__':unittest.main()
