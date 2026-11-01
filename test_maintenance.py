# Disable request throttling in high-volume integration tests only.
import os
os.environ.setdefault('LIBRAAI_AUTH_THROTTLE','0')
import unittest, tempfile, os, datetime
import server
from advanced_server import upgrade,db
from release_server import install
from scheduler import run_workflows,make_verified_backup
class MaintenanceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory()
  cls.previous_db=server.DB
  server.DB=os.path.join(cls.tmp.name,"maintenance.db")
  install()
 @classmethod
 def tearDownClass(cls):
  server.DB=cls.previous_db
  cls.tmp.cleanup()
 def test_backup_restore(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=make_verified_backup(tmp)
   self.assertTrue(os.path.isfile(path))
 def test_workflow_idempotency(self):
  with db() as c:
   uid=c.execute("INSERT INTO users(email,name,role,salt,hash) VALUES(?,?,?,?,?)",('test-'+os.urandom(8).hex()+'@example.com','Test','merchant','a','b')).lastrowid
   wid=c.execute("INSERT INTO workflows(user_id,name,trigger_name,action_name,enabled) VALUES(?,?,?,?,1)",(uid,'Overdue','task_overdue','notify_owner')).lastrowid
   c.execute('INSERT INTO planner(user_id,task,due,minutes) VALUES(?,?,?,?)',(uid,'Finish chapter','2020-01-01',25))
  self.assertGreaterEqual(run_workflows('2026-10-28'),1)
  self.assertEqual(run_workflows('2026-10-28'),0)
  with db() as c:
   self.assertEqual(c.execute('SELECT COUNT(*) FROM workflow_runs WHERE workflow_id=?',(wid,)).fetchone()[0],1)
if __name__=='__main__':unittest.main()
