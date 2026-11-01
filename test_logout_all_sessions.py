import unittest,tempfile,os,time,hashlib,secrets
from unittest.mock import patch
import server

class LogoutAllSessionsTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.patcher=patch.object(server,'DB',os.path.join(self.tmp.name,'test.db'))
  self.patcher.start()
  server.init()
  salt=secrets.token_hex(16)
  with server.db() as c:
   c.execute('INSERT INTO users(email,name,role,salt,hash) VALUES(?,?,?,?,?)',('sessions@example.org','Sessions','customer',salt,server.password('strong-password-123',salt)))
   self.uid=c.execute('SELECT id FROM users WHERE email=?',('sessions@example.org',)).fetchone()[0]
   c.executemany('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)',[(hashlib.sha256(str(i).encode()).hexdigest(),self.uid,int(time.time())+3600) for i in range(3)])
 def tearDown(self):
  self.patcher.stop();self.tmp.cleanup()
 def count(self):
  with server.db() as c:return c.execute('SELECT COUNT(*) FROM sessions WHERE user_id=?',(self.uid,)).fetchone()[0]
 def test_wrong_password_preserves_sessions(self):
  self.assertFalse(server.revoke_all_sessions(self.uid,'wrong'))
  self.assertEqual(self.count(),3)
 def test_correct_password_revokes_every_session(self):
  self.assertTrue(server.revoke_all_sessions(self.uid,'strong-password-123'))
  self.assertEqual(self.count(),0)
 def test_empty_password_is_rejected(self):
  self.assertFalse(server.revoke_all_sessions(self.uid,''))
  self.assertEqual(self.count(),3)
 def test_nonexistent_user_rejected(self):
  self.assertFalse(server.revoke_all_sessions(self.uid+999,'strong-password-123'))
  self.assertEqual(self.count(),3)

if __name__=='__main__':unittest.main()
