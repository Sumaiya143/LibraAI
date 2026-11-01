# Disable request throttling in high-volume integration tests only.
import os
os.environ.setdefault('LIBRAAI_AUTH_THROTTLE','0')
import unittest,uuid
from test_reading_goals import GoalTests
from server import db
class WeeklyGoalTests(GoalTests):
 def test_weekly_count_and_no_double_count(self):
  self.login()
  self.req('/api/reading-goals',{'weekly_books':2})
  with db() as c:
   c.execute("INSERT INTO books(title,author,category,description,price,approved) VALUES('Test title','Test author','Science','test',0,1)")
   bid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
  self.assertEqual(self.req('/api/reading-progress',{'book_id':bid,'percent':100})[0],200)
  self.req('/api/reading-progress',{'book_id':bid,'percent':100})
  result=self.req('/api/reading-goals')[1]
  self.assertEqual(result['completed_this_week'],1)
  self.assertEqual(result['remaining_this_week'],1)
  self.assertEqual(result['weekly_percent'],50)
if __name__=='__main__':unittest.main()
