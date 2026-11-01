# Disable request throttling in high-volume integration tests only.
import os
os.environ.setdefault('LIBRAAI_AUTH_THROTTLE','0')
import unittest,threading,tempfile,os,urllib.request,json
from http.server import ThreadingHTTPServer
import server,catalog_server
class CatalogExperienceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();server.DB=os.path.join(cls.tmp.name,'catalog.db');catalog_server.migrate();cls.http=ThreadingHTTPServer(('127.0.0.1',0),catalog_server.CatalogHandler);cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start();cls.url='http://127.0.0.1:'+str(cls.http.server_port)
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.tmp.cleanup()
 def get(self,path):
  with urllib.request.urlopen(self.url+path) as r:return r.status,r.read().decode()
 def test_catalog_page(self):self.assertIn('Find your next great read',self.get('/catalog.html')[1])
 def test_catalog_css(self):self.assertIn('.book',self.get('/catalog-experience.css')[1])
 def test_catalog_js(self):self.assertIn('/api/catalog/v2',self.get('/catalog-experience.js')[1])
 def test_catalog_api(self):self.assertIn('items',json.loads(self.get('/api/catalog/v2?page=1&limit=12')[1]))
 def test_home_links_catalog(self):self.assertIn('/catalog.html',self.get('/')[1])
 def test_invalid_page(self):
  from urllib.error import HTTPError
  with self.assertRaises(HTTPError) as c:self.get('/api/catalog/v2?page=-1')
  self.assertEqual(c.exception.code,400)
if __name__=='__main__':unittest.main(verbosity=2)
