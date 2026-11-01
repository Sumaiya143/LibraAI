"""Extended, local-first LibraAI modules. No simulated payment confirmations."""
import json,sqlite3,os,random,re,html,base64,uuid,mimetypes
from urllib.parse import urlparse,parse_qs
from server import Handler,db,init,ROOT,ThreadingHTTPServer

def setup():
 init()
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,body TEXT NOT NULL,created TEXT DEFAULT CURRENT_TIMESTAMP);CREATE TABLE IF NOT EXISTS clubs(id INTEGER PRIMARY KEY,name TEXT UNIQUE,description TEXT);CREATE TABLE IF NOT EXISTS memberships(user_id INTEGER,club_id INTEGER,PRIMARY KEY(user_id,club_id));CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,title TEXT,date TEXT,description TEXT);CREATE TABLE IF NOT EXISTS subscriptions(user_id INTEGER PRIMARY KEY,plan TEXT NOT NULL DEFAULT 'free',status TEXT NOT NULL DEFAULT 'inactive');CREATE TABLE IF NOT EXISTS reading_progress(user_id INTEGER,book_id INTEGER,percent INTEGER DEFAULT 0,updated TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,book_id));CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,branch TEXT,status TEXT DEFAULT 'requested',created TEXT DEFAULT CURRENT_TIMESTAMP);CREATE TABLE IF NOT EXISTS branches(id INTEGER PRIMARY KEY,name TEXT,city TEXT);CREATE TABLE IF NOT EXISTS study_cards(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,question TEXT,answer TEXT);CREATE TABLE IF NOT EXISTS book_content(book_id INTEGER PRIMARY KEY,content TEXT,format TEXT DEFAULT 'text',rights_confirmed INTEGER DEFAULT 0);CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY,actor_id INTEGER,action TEXT,object_id INTEGER,created TEXT DEFAULT CURRENT_TIMESTAMP);''')
  # Backward-compatible migration: persist reader page/location alongside percent.
  progress_columns={row['name'] for row in c.execute('PRAGMA table_info(reading_progress)').fetchall()}
  for column, definition in (('page','INTEGER NOT NULL DEFAULT 0'),('location',"TEXT NOT NULL DEFAULT ''"),('file_id','INTEGER'),('audio_seconds','REAL NOT NULL DEFAULT 0')):
   if column not in progress_columns:c.execute(f'ALTER TABLE reading_progress ADD COLUMN {column} {definition}')
  if not c.execute('SELECT 1 FROM clubs').fetchone():c.executemany('INSERT INTO clubs(name,description) VALUES(?,?)',[('Fantasy Lovers','Fantasy and science fiction reading circle'),('Business Readers','Nonfiction and career discussions'),('Manga & Comics','Comics readers community')])
  if not c.execute('SELECT 1 FROM branches').fetchone():c.executemany('INSERT INTO branches(name,city) VALUES(?,?)',[('Dhaka Central Library','Dhaka'),('Chattogram Library','Chattogram'),('Sylhet Reading Hub','Sylhet')])
UPLOAD=os.path.join(ROOT,'private_uploads')
os.makedirs(UPLOAD,exist_ok=True)
ALLOWED={'pdf':'application/pdf','epub':'application/epub+zip','mp3':'audio/mpeg','m4a':'audio/mp4','ogg':'audio/ogg','png':'image/png','jpg':'image/jpeg','webp':'image/webp','cbz':'application/vnd.comicbook+zip'}
def files_setup():
 with db() as c:
  c.execute("CREATE TABLE IF NOT EXISTS book_files(id INTEGER PRIMARY KEY,book_id INTEGER NOT NULL,kind TEXT NOT NULL,filename TEXT NOT NULL,original_name TEXT NOT NULL,created TEXT DEFAULT CURRENT_TIMESTAMP)")
  c.execute("CREATE TABLE IF NOT EXISTS bookmarks(user_id INTEGER,book_id INTEGER,location TEXT,PRIMARY KEY(user_id,book_id))")
class Advanced(Handler):
 def body(self):
  if urlparse(self.path).path!='/api/extra/upload':return super().body()
  try:
   n=int(self.headers.get('Content-Length','0'))
   if n<=0 or n>12*1024*1024:return {}
   return json.loads(self.rfile.read(n))
  except:return {}
 def do_GET(self):
  p=urlparse(self.path).path;u=self.user()
  if p.startswith('/api/file/'):
   if not u:return self.send(401,{'error':'Sign in required'})
   try:fid=int(p.rsplit('/',1)[-1])
   except:return self.send(400,{'error':'Invalid file'})
   with db() as c:
    f=c.execute('SELECT * FROM book_files WHERE id=?',(fid,)).fetchone()
    if not f:return self.send(404,{'error':'File not found'})
    owned=c.execute('SELECT 1 FROM library WHERE user_id=? AND book_id=?',(u['id'],f['book_id'])).fetchone()
    publisher=c.execute('SELECT merchant_id FROM books WHERE id=?',(f['book_id'],)).fetchone()
    if not owned and u['role']!='admin' and (not publisher or publisher['merchant_id']!=u['id']):return self.send(403,{'error':'No access to this licensed content'})
   path=os.path.join(UPLOAD,f['filename'])
   if not os.path.isfile(path):return self.send(404,{'error':'File missing'})
   data=open(path,'rb').read();typ=mimetypes.guess_type(f['original_name'])[0] or 'application/octet-stream'
   self.send_response(200);self.send_header('Content-Type',typ);self.send_header('Content-Disposition','inline');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','private, no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
  if p.startswith('/api/extra/'):
   kind=p.split('/')[-1]
   with db() as c:
    if kind=='files':
     if not u:return self.send(401,{'error':'Sign in required'})
     try:bid=int(parse_qs(urlparse(self.path).query).get('book_id',[0])[0])
     except:return self.send(400,{'error':'Invalid book'})
     owned=c.execute('SELECT 1 FROM library WHERE user_id=? AND book_id=?',(u['id'],bid)).fetchone()
     book=c.execute('SELECT merchant_id FROM books WHERE id=?',(bid,)).fetchone()
     if not book or (not owned and u['role']!='admin' and book['merchant_id']!=u['id']):return self.send(403,{'error':'Access denied'})
     return self.send(200,[dict(x) for x in c.execute('SELECT id,book_id,kind,original_name,created FROM book_files WHERE book_id=?',(bid,))])
    if kind=='bookmark':
     if not u:return self.send(401,{'error':'Sign in required'})
     bid=int(parse_qs(urlparse(self.path).query).get('book_id',[0])[0]);r=c.execute('SELECT location FROM bookmarks WHERE user_id=? AND book_id=?',(u['id'],bid)).fetchone();return self.send(200,dict(r) if r else {'location':''})
    if kind=='community':
     rows=c.execute('SELECT posts.id,posts.body,posts.created,users.name FROM posts JOIN users ON users.id=posts.user_id ORDER BY posts.id DESC LIMIT 100').fetchall();return self.send(200,[dict(x) for x in rows])
    if kind in ('clubs','events','branches'):return self.send(200,[dict(x) for x in c.execute('SELECT * FROM '+kind).fetchall()])
    if not u:return self.send(401,{'error':'Sign in required'})
    if kind=='progress':
     query=parse_qs(urlparse(self.path).query)
     if query.get('book_id'):
      try:bid=int(query['book_id'][0])
      except (TypeError,ValueError):return self.send(400,{'error':'Invalid book'})
      if not c.execute('SELECT 1 FROM library WHERE user_id=? AND book_id=?',(u['id'],bid)).fetchone():return self.send(403,{'error':'Book not in bookshelf'})
      row=c.execute('SELECT book_id,percent,page,location,file_id,audio_seconds,updated FROM reading_progress WHERE user_id=? AND book_id=?',(u['id'],bid)).fetchone()
      return self.send(200,dict(row) if row else {'book_id':bid,'percent':0,'page':0,'location':'','file_id':None,'audio_seconds':0,'updated':None})
     return self.send(200,[dict(x) for x in c.execute('SELECT reading_progress.*,books.title FROM reading_progress JOIN books ON books.id=reading_progress.book_id WHERE user_id=?',(u['id'],))])
    if kind=='cards':return self.send(200,[dict(x) for x in c.execute('SELECT * FROM study_cards WHERE user_id=?',(u['id'],))])
    if kind=='requests':return self.send(200,[dict(x) for x in c.execute('SELECT requests.*,books.title FROM requests JOIN books ON books.id=requests.book_id WHERE user_id=?',(u['id'],))])
    if kind=='subscription':
     r=c.execute('SELECT plan,status FROM subscriptions WHERE user_id=?',(u['id'],)).fetchone();return self.send(200,dict(r) if r else {'plan':'free','status':'inactive'})
    if kind=='analytics':
     return self.send(200,{'books':c.execute('SELECT count(*) FROM books WHERE approved=1').fetchone()[0],'my_books':c.execute('SELECT count(*) FROM library WHERE user_id=?',(u['id'],)).fetchone()[0],'notes':c.execute('SELECT count(*) FROM notes WHERE user_id=?',(u['id'],)).fetchone()[0],'posts':c.execute('SELECT count(*) FROM posts WHERE user_id=?',(u['id'],)).fetchone()[0],'pending_orders':c.execute("SELECT count(*) FROM orders WHERE user_id=? AND status='pending'",(u['id'],)).fetchone()[0]})
    if kind=='moderation':
     if u['role']!='admin':return self.send(403,{'error':'Admin only'})
     return self.send(200,[dict(x) for x in c.execute('SELECT * FROM books WHERE approved=0')])
    if kind=='reader':
     try:bid=int(parse_qs(urlparse(self.path).query).get('book_id',[0])[0])
     except:return self.send(400,{'error':'Invalid book'})
     book=c.execute('SELECT price,approved FROM books WHERE id=?',(bid,)).fetchone()
     owned=c.execute('SELECT 1 FROM library WHERE user_id=? AND book_id=?',(u['id'],bid)).fetchone()
     if not book or not book['approved'] or not owned:return self.send(403,{'error':'Book must be in your bookshelf'})
     r=c.execute('SELECT content,format FROM book_content WHERE book_id=? AND rights_confirmed=1',(bid,)).fetchone()
     return self.send(200,dict(r) if r else {'content':'No licensed digital content has been uploaded for this title.','format':'unavailable'})
   return self.send(404,{'error':'Unknown module'})
  return super().do_GET()
 def do_POST(self):
  p=urlparse(self.path).path
  if not p.startswith('/api/extra/'):return super().do_POST()
  u=self.user();b=self.body();kind=p.split('/')[-1]
  if not u:return self.send(401,{'error':'Sign in required'})
  with db() as c:
   if kind=='upload':
    if u['role'] not in ('merchant','admin'):return self.send(403,{'error':'Publisher role required'})
    try:bid=int(b.get('book_id',0));name=str(b.get('filename',''))[:160];data=base64.b64decode(b.get('base64',''),validate=True)
    except:return self.send(400,{'error':'Invalid file encoding'})
    ext=name.rsplit('.',1)[-1].lower() if '.' in name else ''
    if ext not in ALLOWED or len(data)>8*1024*1024 or not data:return self.send(400,{'error':'Use PDF, EPUB, MP3, M4A, OGG, PNG, JPG, WEBP, max 8 MB per upload'})
    from upload_security import inspect_upload
    accepted, scan_status, scan_message = inspect_upload(name, data)
    if not accepted:
     code=503 if scan_status=='unavailable' else 415 if scan_status=='invalid' else 400
     return self.send(code,{'error':scan_message,'scan_status':scan_status})
    if not b.get('rights_confirmed'):return self.send(400,{'error':'Confirm distribution rights'})
    r=c.execute('SELECT merchant_id FROM books WHERE id=?',(bid,)).fetchone()
    if not r or (u['role']!='admin' and r['merchant_id']!=u['id']):return self.send(403,{'error':'Not your book'})
    stored=uuid.uuid4().hex+'.'+ext;open(os.path.join(UPLOAD,stored),'wb').write(data)
    c.execute('INSERT INTO book_files(book_id,kind,filename,original_name) VALUES(?,?,?,?)',(bid,ext,stored,name))
   elif kind=='bookmark':
    bid=int(b.get('book_id',0));loc=str(b.get('location',''))[:300]
    if not c.execute('SELECT 1 FROM library WHERE user_id=? AND book_id=?',(u['id'],bid)).fetchone():return self.send(403,{'error':'Book not owned'})
    c.execute('INSERT INTO bookmarks(user_id,book_id,location) VALUES(?,?,?) ON CONFLICT(user_id,book_id) DO UPDATE SET location=excluded.location',(u['id'],bid,loc))
   elif kind=='post':
    body=str(b.get('body','')).strip()[:1500]
    if len(body)<3:return self.send(400,{'error':'Post is too short'})
    c.execute('INSERT INTO posts(user_id,body) VALUES(?,?)',(u['id'],body))
   elif kind=='join':
    club=int(b.get('club_id',0))
    if not c.execute('SELECT 1 FROM clubs WHERE id=?',(club,)).fetchone():return self.send(404,{'error':'Club not found'})
    c.execute('INSERT OR IGNORE INTO memberships VALUES(?,?)',(u['id'],club))
   elif kind=='progress':
    try:
     bid=int(b.get('book_id',0));pct=int(b.get('percent',0));page=int(b.get('page',0));audio_seconds=float(b.get('audio_seconds',0));file_id=int(b['file_id']) if b.get('file_id') not in (None,'') else None
    except (TypeError,ValueError):return self.send(400,{'error':'Book, percent, page and audio position must be valid numbers'})
    location=str(b.get('location',''))[:2000]
    if not 0<=pct<=100:return self.send(400,{'error':'Percent must be 0-100'})
    if not 0<=page<=1000000:return self.send(400,{'error':'Page must be between 0 and 1000000'})
    if not 0<=audio_seconds<=315360000:return self.send(400,{'error':'Audio position must be between 0 and 315360000 seconds'})
    if not c.execute('SELECT 1 FROM library WHERE user_id=? AND book_id=?',(u['id'],bid)).fetchone():return self.send(403,{'error':'Book not in bookshelf'})
    if file_id is not None and not c.execute('SELECT 1 FROM book_files WHERE id=? AND book_id=?',(file_id,bid)).fetchone():return self.send(400,{'error':'Reader file does not belong to this book'})
    c.execute('INSERT INTO reading_progress(user_id,book_id,percent,page,location,file_id,audio_seconds) VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id,book_id) DO UPDATE SET percent=excluded.percent,page=excluded.page,location=excluded.location,file_id=excluded.file_id,audio_seconds=excluded.audio_seconds,updated=CURRENT_TIMESTAMP',(u['id'],bid,pct,page,location,file_id,audio_seconds))
   elif kind=='card':
    q=str(b.get('question','')).strip()[:500];a=str(b.get('answer','')).strip()[:1000]
    if not q or not a:return self.send(400,{'error':'Question and answer required'})
    c.execute('INSERT INTO study_cards(user_id,book_id,question,answer) VALUES(?,?,?,?)',(u['id'],int(b.get('book_id',0)),q,a))
   elif kind=='request':
    bid=int(b.get('book_id',0));branch=str(b.get('branch',''))[:120]
    if not c.execute('SELECT 1 FROM books WHERE id=? AND approved=1',(bid,)).fetchone():return self.send(404,{'error':'Book unavailable'})
    if not c.execute('SELECT 1 FROM branches WHERE name=?',(branch,)).fetchone():return self.send(400,{'error':'Choose a listed branch'})
    c.execute('INSERT INTO requests(user_id,book_id,branch) VALUES(?,?,?)',(u['id'],bid,branch))
   elif kind=='moderate':
    if u['role']!='admin':return self.send(403,{'error':'Admin only'})
    bid=int(b.get('book_id',0));approve=bool(b.get('approve'))
    if approve:c.execute('UPDATE books SET approved=1 WHERE id=?',(bid,))
    else:c.execute('DELETE FROM books WHERE id=? AND approved=0',(bid,))
    c.execute('INSERT INTO audit_log(actor_id,action,object_id) VALUES(?,?,?)',(u['id'],'approve' if approve else 'reject',bid))
   elif kind=='content':
    if u['role'] not in ('merchant','admin'):return self.send(403,{'error':'Publisher only'})
    bid=int(b.get('book_id',0));content=str(b.get('content',''))
    if len(content)>200000 or not b.get('rights_confirmed'):return self.send(400,{'error':'Rights confirmation required; max 200k characters'})
    r=c.execute('SELECT merchant_id FROM books WHERE id=?',(bid,)).fetchone()
    if not r or (u['role']!='admin' and r['merchant_id']!=u['id']):return self.send(403,{'error':'Not your listing'})
    c.execute('INSERT INTO book_content(book_id,content,rights_confirmed) VALUES(?,?,1) ON CONFLICT(book_id) DO UPDATE SET content=excluded.content,rights_confirmed=1',(bid,content))
   elif kind=='study':
    text=str(b.get('text','')).strip()[:10000]
    if len(text)<30:return self.send(400,{'error':'Provide at least 30 characters of your own text'})
    words=re.findall(r"[A-Za-z]{4,}",text.lower());freq={w:words.count(w) for w in set(words)}
    top=sorted(freq,key=lambda w:-freq[w])[:8];sentences=re.split(r'(?<=[.!?])\s+',text)
    return self.send(200,{'mode':'local-extractive','summary':' '.join(sentences[:3])[:900],'keywords':top,'question':'What is the main idea of the passage?','answer':sentences[0][:500]})
   elif kind=='subscription':return self.send(400,{'error':'Subscription checkout is disabled until a verified payment provider is configured.'})
   elif kind=='payment':return self.send(503,{'error':'No payment provider credentials configured. Never mark orders paid without verified server-side confirmation.'})
   else:return self.send(404,{'error':'Unknown module'})
  return self.send(201,{'ok':True})
if __name__=='__main__':
 setup();files_setup();port=int(os.getenv('PORT','8000'));print(f'LibraAI Extended: http://127.0.0.1:{port}');ThreadingHTTPServer(('127.0.0.1',port),Advanced).serve_forever()
