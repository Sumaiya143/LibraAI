# Disable request throttling in high-volume integration tests only.
import os
os.environ.setdefault('LIBRAAI_AUTH_THROTTLE','0')
import unittest,tempfile,os,threading,urllib.request,json
from http.server import ThreadingHTTPServer
import server
from catalog_server import CatalogHandler,migrate
class CatalogTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();server.DB=os.path.join(cls.tmp.name,'test.db')
  migrate();cls.http=ThreadingHTTPServer(('127.0.0.1',0),CatalogHandler)
  cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.tmp.cleanup()
 def get(self,path):
  try:
   with urllib.request.urlopen('http://127.0.0.1:'+str(self.http.server_port)+path) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def test_default_discovery_shelf_has_25_books_and_is_idempotent(self):
  with server.db() as c: before=c.execute('SELECT COUNT(*) FROM books WHERE approved=1').fetchone()[0]
  self.assertGreaterEqual(before,25)
  migrate()
  with server.db() as c: after=c.execute('SELECT COUNT(*) FROM books WHERE approved=1').fetchone()[0]
  self.assertEqual(before,after)
 def test_pages(self):
  code,body=self.get('/api/catalog/v2?limit=3&page=2');self.assertEqual(code,200);self.assertEqual(len(body['items']),3);self.assertGreaterEqual(body['total'],6)
 def test_search(self):
  code,body=self.get('/api/catalog/v2?q=Dune');self.assertEqual(code,200);self.assertTrue(any('Dune' in x['title'] for x in body['items']))
 def test_filter(self):
  code,body=self.get('/api/catalog/v2?category=History');self.assertEqual(code,200);self.assertTrue(all(x['category']=='History' for x in body['items']))
 def test_invalid(self):
  self.assertEqual(self.get('/api/catalog/v2?limit=999')[0],400)
  self.assertEqual(self.get('/api/catalog/v2?sort=unknown')[0],400)
 def test_no_unapproved(self):
  with server.db() as c:c.execute("INSERT INTO books(title,author,category,approved) VALUES('SecretDraft','X','History',0)")
  self.assertEqual(self.get('/api/catalog/v2?q=SecretDraft')[1]['total'],0)
if __name__=='__main__':unittest.main(verbosity=2)
