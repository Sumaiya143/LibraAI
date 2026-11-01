# Disable request throttling in high-volume integration tests only.
import os
os.environ.setdefault('LIBRAAI_AUTH_THROTTLE','0')
import unittest,threading,tempfile,os,json,urllib.request,urllib.error,http.cookiejar
from http.server import ThreadingHTTPServer
import server,catalog_server
class GoalTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();server.DB=os.path.join(cls.temp.name,'test.db');catalog_server.migrate();cls.http=ThreadingHTTPServer(('127.0.0.1',0),catalog_server.CatalogHandler);threading.Thread(target=cls.http.serve_forever,daemon=True).start();cls.url='http://127.0.0.1:'+str(cls.http.server_port)
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.temp.cleanup()
 def setUp(self):
  self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def req(self,path,data=None):
  body=json.dumps(data).encode() if data is not None else None
  try:
   with self.opener.open(urllib.request.Request(self.url+path,body,headers={'Content-Type':'application/json'}),timeout=5) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def login(self):
  import uuid
  email=str(uuid.uuid4())+'@example.org';self.assertEqual(self.req('/api/signup',{'name':'Reader','email':email,'password':'strong-password-123','role':'customer'})[0],201)
  self.assertEqual(self.req('/api/login',{'email':email,'password':'strong-password-123'})[0],200)
 def test_goal_requires_login(self):self.assertEqual(self.req('/api/reading-goals')[0],401)
 def test_goal_create_and_read(self):
  self.login();self.assertEqual(self.req('/api/reading-goals',{'weekly_books':3})[0],200);self.assertEqual(self.req('/api/reading-goals')[1]['weekly_books'],3)
 def test_goal_rejects_invalid(self):
  self.login();self.assertEqual(self.req('/api/reading-goals',{'weekly_books':51})[0],400)
 def test_user_isolation(self):
  self.login();self.req('/api/reading-goals',{'weekly_books':7});other=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));self.opener=other;self.login();self.assertIsNone(self.req('/api/reading-goals')[1]['weekly_books'])
if __name__=='__main__':unittest.main(verbosity=2)
