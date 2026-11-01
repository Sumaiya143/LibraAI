# Disable request throttling in high-volume integration tests only.
import os
os.environ.setdefault('LIBRAAI_AUTH_THROTTLE','0')
import unittest,threading,urllib.request,urllib.error,json,tempfile,os
from http.server import ThreadingHTTPServer
import server,catalog_server
class Handoff(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();server.DB=os.path.join(cls.tmp.name,'test.db');catalog_server.migrate();cls.http=ThreadingHTTPServer(('127.0.0.1',0),catalog_server.CatalogHandler);cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start();cls.url='http://127.0.0.1:'+str(cls.http.server_port)
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.tmp.cleanup()
 def get(self,path):
  with urllib.request.urlopen(self.url+path) as r:return r.status,r.read().decode()
 def test_home(self):self.assertIn('AI-Powered',self.get('/')[1])
 def test_account(self):self.assertIn('Create Account',self.get('/account.html')[1])
 def test_js(self):self.assertIn('/api/',self.get('/account.js')[1])
 def test_catalog(self):self.assertIn('items',json.loads(self.get('/api/catalog/v2')[1]))
 def test_signup(self):
  body=json.dumps({'name':'Sample','email':'sample@example.org','password':'a-very-long-passphrase','role':'merchant'}).encode();req=urllib.request.Request(self.url+'/api/signup',body,{'Content-Type':'application/json'});self.assertEqual(urllib.request.urlopen(req).status,201)
if __name__=='__main__':unittest.main(verbosity=2)
