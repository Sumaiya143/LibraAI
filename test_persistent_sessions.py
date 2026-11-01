# Disable request throttling in high-volume integration tests only.
import os
os.environ.setdefault('LIBRAAI_AUTH_THROTTLE','0')
import unittest, tempfile, os, sqlite3, hashlib, time
from unittest.mock import patch
import server

class PersistentSessionsTest(unittest.TestCase):
 def test_session_schema_and_hash_storage(self):
  with tempfile.TemporaryDirectory() as d:
   with patch.object(server,'DB',os.path.join(d,'test.db')):
    server.init()
    with server.db() as c:
     c.execute('INSERT INTO users(email,name,role,salt,hash) VALUES(?,?,?,?,?)',('test@example.org','Test','customer','a','b'))
     uid=c.execute('SELECT id FROM users WHERE email=?',('test@example.org',)).fetchone()[0]
     token='sample-secret-session-token'
     c.execute('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid,int(time.time())+300))
     self.assertEqual(c.execute('SELECT user_id FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()[0],uid)
     self.assertEqual(c.execute('SELECT COUNT(*) FROM sessions WHERE token_hash=?',(token,)).fetchone()[0],0)
if __name__=='__main__': unittest.main()
