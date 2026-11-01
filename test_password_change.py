import hashlib,os,secrets,tempfile,time,unittest
from unittest.mock import patch
import server

class PasswordChangeTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.patch=patch.object(server,'DB',os.path.join(self.temp.name,'users.db'))
  self.patch.start();server.init()
  salt=secrets.token_hex(16)
  with server.db() as c:
   c.execute('INSERT INTO users(email,name,role,salt,hash) VALUES(?,?,?,?,?)',('password@example.com','Example','customer',salt,server.password('previous-secret-123',salt)))
   self.uid=c.execute('SELECT id FROM users WHERE email=?',('password@example.com',)).fetchone()[0]
   c.executemany('INSERT INTO sessions VALUES(?,?,?)',[(hashlib.sha256(str(i).encode()).hexdigest(),self.uid,int(time.time())+10000) for i in range(2)])
 def tearDown(self):
  self.patch.stop();self.temp.cleanup()
 def count(self):
  with server.db() as c:return c.execute('SELECT COUNT(*) FROM sessions WHERE user_id=?',(self.uid,)).fetchone()[0]
 def valid(self,p):
  with server.db() as c:r=c.execute('SELECT salt,hash FROM users WHERE id=?',(self.uid,)).fetchone()
  return secrets.compare_digest(r['hash'],server.password(p,r['salt']))
 def test_success_changes_hash_and_revokes_sessions(self):
  self.assertTrue(server.change_account_password(self.uid,'previous-secret-123','different-secret-456'))
  self.assertEqual(self.count(),0)
  self.assertFalse(self.valid('previous-secret-123'))
  self.assertTrue(self.valid('different-secret-456'))
 def test_wrong_current_password_does_not_modify_account(self):
  self.assertFalse(server.change_account_password(self.uid,'wrong-password','different-secret-456'))
  self.assertEqual(self.count(),2)
  self.assertTrue(self.valid('previous-secret-123'))
 def test_short_new_password_rejected(self):
  self.assertFalse(server.change_account_password(self.uid,'previous-secret-123','short'))
  self.assertEqual(self.count(),2)
 def test_reusing_password_rejected(self):
  self.assertFalse(server.change_account_password(self.uid,'previous-secret-123','previous-secret-123'))
  self.assertEqual(self.count(),2)
 def test_invalid_types_rejected(self):
  self.assertFalse(server.change_account_password(self.uid,None,['bad']))
  self.assertEqual(self.count(),2)

if __name__=='__main__':unittest.main()
