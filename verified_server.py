"""Verified development entrypoint: genuine public statistics and review summaries."""
import os, json, urllib.parse
from http.server import ThreadingHTTPServer
from ebook_reader import ReaderRelease
from release_server import install
from scheduler import start_maintenance
from server import db

class VerifiedHandler(ReaderRelease):
 def do_GET(self):
  path=urllib.parse.urlparse(self.path).path
  if path=='/api/public/stats':
   with db() as c:
    books=c.execute('SELECT COUNT(*) FROM books WHERE approved=1').fetchone()[0]
    readers=c.execute("SELECT COUNT(*) FROM users WHERE role='customer'").fetchone()[0]
    reviews=c.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]
    ratings=[dict(r) for r in c.execute('SELECT book_id,COUNT(*) review_count,ROUND(AVG(rating),2) average_rating FROM reviews GROUP BY book_id')]
   return self.send(200,{'books':books,'readers':readers,'reviews':reviews,'ratings':ratings,'note':'Counts reflect local database only; not global adoption.'})
  return super().do_GET()

if __name__=='__main__':
 install()
 if os.getenv('LIBRA_SCHEDULER','0')=='1':start_maintenance()
 port=int(os.getenv('PORT','8000'))
 print('LibraAI development server: http://127.0.0.1:'+str(port))
 ThreadingHTTPServer(('127.0.0.1',port),VerifiedHandler).serve_forever()
