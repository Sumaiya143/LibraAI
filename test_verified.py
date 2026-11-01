# Disable request throttling in high-volume integration tests only.
import os
os.environ.setdefault('LIBRAAI_AUTH_THROTTLE','0')
"""Isolated end-to-end smoke tests; uses a temporary DB and HTTP server."""
import os, tempfile, threading, json, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
import server
from verified_server import VerifiedHandler
from release_server import install

def main():
 with tempfile.TemporaryDirectory() as temp:
  server.DB=os.path.join(temp,'test.db')
  # The chained backend uses the same database file through imported server.db.
  install()
  srv=ThreadingHTTPServer(('127.0.0.1',0),VerifiedHandler)
  thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
  base=f'http://127.0.0.1:{srv.server_port}'
  def get(path):
   with urllib.request.urlopen(base+path,timeout=5) as response:return response.status,response.read()
  try:
   status,raw=get('/api/public/stats');assert status==200
   stats=json.loads(raw);assert stats['books']>=8 and stats['readers']==0 and stats['reviews']==0
   status,raw=get('/');assert status==200 and b'AI-Powered' in raw
   status,raw=get('/home-premium.js');assert status==200 and b'public/stats' in raw
   status,raw=get('/api/books');assert status==200 and len(json.loads(raw))>=8
   status,raw=get('/reader.html');assert status==200
   print('PASS: public stats, homepage, JS, book catalog, reader route (5 checks)')
  finally:srv.shutdown();srv.server_close()
if __name__=='__main__':main()
