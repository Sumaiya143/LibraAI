from pathlib import Path
import os,json,sqlite3,hashlib,hmac,secrets,datetime,mimetypes,time
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from http.cookies import SimpleCookie
ROOT=os.path.dirname(__file__); DB=os.path.join(ROOT,'libra.db'); SESS={}

class ClosingConnection(sqlite3.Connection):
 """SQLite connection that commits/rolls back and always closes on context exit."""
 def __exit__(self, exc_type, exc_value, traceback):
  try:
   return super().__exit__(exc_type, exc_value, traceback)
  finally:
   self.close()

def db():
 c=sqlite3.connect(DB, timeout=10, factory=ClosingConnection)
 c.row_factory=sqlite3.Row
 return c
def init():
 with db() as c:
  c.execute('CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL,expires_at INTEGER NOT NULL)')
  c.execute('CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)')
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('customer','merchant','admin')),salt TEXT NOT NULL,hash TEXT NOT NULL);CREATE TABLE IF NOT EXISTS books(id INTEGER PRIMARY KEY,title TEXT NOT NULL,author TEXT NOT NULL,category TEXT NOT NULL,description TEXT DEFAULT '',price REAL DEFAULT 0,merchant_id INTEGER,approved INTEGER DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP);CREATE TABLE IF NOT EXISTS library(user_id INTEGER,book_id INTEGER,PRIMARY KEY(user_id,book_id));CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,body TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,rating INTEGER CHECK(rating BETWEEN 1 AND 5),body TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,amount REAL,status TEXT DEFAULT 'pending',created TEXT DEFAULT CURRENT_TIMESTAMP);''')
  if not c.execute('SELECT 1 FROM books LIMIT 1').fetchone():
   c.executemany('INSERT INTO books(title,author,category,description,price,approved) VALUES(?,?,?,?,?,1)', [('Atomic Habits','James Clear','Self Development','Build better habits with small changes.',12.99),('Dune','Frank Herbert','Science Fiction','Epic science-fiction adventure.',14.99),('The Psychology of Money','Morgan Housel','Finance','Timeless lessons on wealth and behavior.',9.99),('It Ends With Us','Colleen Hoover','Fiction','A contemporary novel.',11.99),('Project Hail Mary','Andy Weir','Science Fiction','A space adventure.',13.99),('The Midnight Library','Matt Haig','Fiction','A story about life and choices.',10.99),('Deep Work','Cal Newport','Productivity','Focus in a distracted world.',12.99),('Sapiens','Yuval Noah Harari','History','A brief history of humankind.',15.99)])
def password(p,s):return hashlib.pbkdf2_hmac('sha256',p.encode(),bytes.fromhex(s),250000).hex()
def revoke_all_sessions(user_id, supplied_password):
 """Require password reauthentication before invalidating every device session."""
 if not isinstance(supplied_password,str) or not supplied_password:
  return False
 with db() as c:
  row=c.execute('SELECT salt,hash FROM users WHERE id=?',(user_id,)).fetchone()
  if not row or not hmac.compare_digest(row['hash'],password(supplied_password,row['salt'])):
   return False
  c.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
 return True
def change_account_password(user_id, current_password, new_password):
 """Atomically change password and invalidate all sessions after reauthentication."""
 if not isinstance(current_password,str) or not isinstance(new_password,str):
  return False
 if len(new_password)<12 or len(new_password)>1024 or new_password==current_password:
  return False
 with db() as c:
  c.execute('BEGIN IMMEDIATE')
  row=c.execute('SELECT salt,hash FROM users WHERE id=?',(user_id,)).fetchone()
  if not row or not hmac.compare_digest(row['hash'],password(current_password,row['salt'])):
   return False
  salt=secrets.token_hex(16)
  c.execute('UPDATE users SET salt=?,hash=? WHERE id=?',(salt,password(new_password,salt),user_id))
  c.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
 return True

class Handler(BaseHTTPRequestHandler):
 def send(self,status,obj,cookie=None):
  raw=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','strict-origin-when-cross-origin');self.send_header('X-Frame-Options','DENY');
  if cookie:self.send_header('Set-Cookie',cookie)
  self.end_headers();self.wfile.write(raw)
 def body(self):
  try:
   n=int(self.headers.get('Content-Length','0'))
   if n<0 or n>100000:return {}
   payload=json.loads(self.rfile.read(n))
   return payload if isinstance(payload,dict) else {}
  except (ValueError,TypeError,UnicodeDecodeError):return {}
 def user(self):
  ck=SimpleCookie()
  try:ck.load(self.headers.get('Cookie',''))
  except:return None
  token=ck['sid'].value if 'sid' in ck else ''
  if not token:return None
  digest=hashlib.sha256(token.encode()).hexdigest()
  with db() as c:
   session=c.execute('SELECT user_id FROM sessions WHERE token_hash=? AND expires_at>?',(digest,int(time.time()))).fetchone()
   if not session:return None
   return c.execute('SELECT id,email,name,role FROM users WHERE id=?',(session['user_id'],)).fetchone()
 def do_GET(self):
  p=urlparse(self.path);u=self.user()
  if p.path=='/api/me':return self.send(200,dict(u) if u else None)
  if p.path=='/api/books':
   q=parse_qs(p.query).get('q',[''])[0];cat=parse_qs(p.query).get('category',[''])[0]
   with db() as c: rows=c.execute('SELECT books.*,users.name merchant FROM books LEFT JOIN users ON users.id=books.merchant_id WHERE approved=1 AND (title LIKE ? OR author LIKE ?) AND (?="" OR category=?) ORDER BY id DESC',('%'+q+'%','%'+q+'%',cat,cat)).fetchall()
   return self.send(200,[dict(r) for r in rows])
  if p.path=='/api/my-books':
   if not u:return self.send(401,{'error':'Sign in required'})
   with db() as c: rows=c.execute('SELECT books.* FROM books JOIN library ON library.book_id=books.id WHERE library.user_id=?',(u['id'],)).fetchall()
   return self.send(200,[dict(r) for r in rows])
  if p.path=='/api/my-listings':
   if not u or u['role'] not in ('merchant','admin'):return self.send(403,{'error':'Merchant access required'})
   with db() as c:rows=c.execute('SELECT * FROM books WHERE merchant_id=?',(u['id'],)).fetchall()
   return self.send(200,[dict(r) for r in rows])
  if p.path=='/api/notes':
   if not u:return self.send(401,{'error':'Sign in required'})
   with db() as c:rows=c.execute('SELECT * FROM notes WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall()
   return self.send(200,[dict(r) for r in rows])
  if p.path=='/api/reviews':
   with db() as c:rows=c.execute('SELECT reviews.*,users.name FROM reviews JOIN users ON users.id=reviews.user_id WHERE book_id=? ORDER BY reviews.id DESC',(parse_qs(p.query).get('book_id',['0'])[0],)).fetchall()
   return self.send(200,[dict(r) for r in rows])
  if p.path=='/api/orders':
   if not u:return self.send(401,{'error':'Sign in required'})
   with db() as c:rows=c.execute('SELECT orders.*,books.title FROM orders JOIN books ON books.id=orders.book_id WHERE user_id=? ORDER BY orders.id DESC',(u['id'],)).fetchall()
   return self.send(200,[dict(r) for r in rows])
  path=os.path.join(ROOT,'static',p.path.lstrip('/') or 'index.html')
  if not os.path.realpath(path).startswith(os.path.realpath(os.path.join(ROOT,'static'))+os.sep):return self.send(404,{'error':'Not found'})
  if not os.path.isfile(path):path=os.path.join(ROOT,'static','index.html')
  raw=Path(path).read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(path)[0] or 'text/html');self.send_header('Content-Length',str(len(raw)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.end_headers();self.wfile.write(raw)
 def do_POST(self):
  p=urlparse(self.path).path;b=self.body();u=self.user()
  if p=='/api/signup':
   name=str(b.get('name','')).strip()[:100];email=str(b.get('email','')).strip().lower();pw=str(b.get('password',''));role=b.get('role')
   if not name or '@' not in email or len(pw)<10 or role not in ('customer','merchant'):return self.send(400,{'error':'Provide name, valid email, 10+ character password, and role'})
   salt=secrets.token_hex(16)
   try:
    with db() as c: c.execute('INSERT INTO users(email,name,role,salt,hash) VALUES(?,?,?,?,?)',(email,name,role,salt,password(pw,salt)))
   except sqlite3.IntegrityError:return self.send(409,{'error':'Email already registered'})
   return self.send(201,{'ok':True})
  if p=='/api/login':
   with db() as c:r=c.execute('SELECT * FROM users WHERE email=?',(str(b.get('email','')).lower(),)).fetchone()
   if not r or not hmac.compare_digest(r['hash'],password(str(b.get('password','')),r['salt'])):return self.send(401,{'error':'Invalid credentials'})
   token=secrets.token_urlsafe(32)
   with db() as c:
    c.execute('DELETE FROM sessions WHERE expires_at<=?',(int(time.time()),))
    c.execute('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),r['id'],int(time.time())+86400))
   return self.send(200,{'ok':True},'sid='+token+'; HttpOnly; SameSite=Lax; Path=/; Max-Age=86400'+('; Secure' if os.getenv('LIBRA_HTTPS')=='1' else ''))
  if p=='/api/logout':
   ck=SimpleCookie();ck.load(self.headers.get('Cookie',''))
   if 'sid' in ck:
    with db() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(ck['sid'].value.encode()).hexdigest(),))
   return self.send(200,{'ok':True},'sid=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0')
  if p=='/api/security/change-password':
   if not u:return self.send(401,{'error':'Sign in required'})
   if not change_account_password(u['id'],b.get('current_password'),b.get('new_password')):
    return self.send(400,{'error':'Invalid current password or new password (minimum 12 characters; must differ)'})
   return self.send(200,{'ok':True,'message':'Password changed; sign in again on all devices'},'sid=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'+('; Secure' if os.getenv('LIBRA_HTTPS')=='1' else ''))
  if p=='/api/security/logout-all':
   if not u:return self.send(401,{'error':'Sign in required'})
   if not revoke_all_sessions(u['id'],b.get('password')):
    return self.send(403,{'error':'Password verification failed'})
   return self.send(200,{'ok':True,'message':'All sessions revoked'},'sid=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'+('; Secure' if os.getenv('LIBRA_HTTPS')=='1' else ''))
  if not u:return self.send(401,{'error':'Please sign in'})
  if p=='/api/books':
   if u['role'] not in ('merchant','admin'):return self.send(403,{'error':'Merchant role required'})
   title=str(b.get('title','')).strip()[:200];author=str(b.get('author','')).strip()[:150];category=str(b.get('category','Fiction'))[:80]
   try:price=float(b.get('price',0))
   except:return self.send(400,{'error':'Invalid price'})
   if not title or not author or price<0 or price>100000:return self.send(400,{'error':'Invalid listing'})
   with db() as c:c.execute('INSERT INTO books(title,author,category,description,price,merchant_id,approved) VALUES(?,?,?,?,?,?,0)',(title,author,category,str(b.get('description',''))[:2000],price,u['id']))
   return self.send(201,{'ok':True,'message':'Submitted for admin review'})
  if p=='/api/notes':
   body=str(b.get('body','')).strip()[:3000]
   if not body:return self.send(400,{'error':'Note is empty'})
   with db() as c:c.execute('INSERT INTO notes(user_id,book_id,body) VALUES(?,?,?)',(u['id'],int(b.get('book_id',1)),body))
   return self.send(201,{'ok':True})
  if p=='/api/reviews':
   try:rating=int(b.get('rating',5));bid=int(b.get('book_id'))
   except:return self.send(400,{'error':'Invalid review'})
   if rating not in range(1,6):return self.send(400,{'error':'Rating must be 1–5'})
   with db() as c:c.execute('INSERT INTO reviews(user_id,book_id,rating,body) VALUES(?,?,?,?)',(u['id'],bid,rating,str(b.get('body',''))[:1000]))
   return self.send(201,{'ok':True})
  if p=='/api/checkout':
   try:bid=int(b.get('book_id'))
   except:return self.send(400,{'error':'Invalid book'})
   with db() as c:
    book=c.execute('SELECT * FROM books WHERE id=? AND approved=1',(bid,)).fetchone()
    if not book:return self.send(404,{'error':'Book unavailable'})
    c.execute('INSERT INTO orders(user_id,book_id,amount) VALUES(?,?,?)',(u['id'],bid,book['price']))
   return self.send(201,{'ok':True,'message':'Order created as pending. No payment has been taken.'})
  if p=='/api/add-free':
   with db() as c:
    r=c.execute('SELECT price FROM books WHERE id=? AND approved=1',(b.get('book_id'),)).fetchone()
    if not r or r['price']!=0:return self.send(403,{'error':'Only free books can be added without payment'})
    c.execute('INSERT OR IGNORE INTO library(user_id,book_id) VALUES(?,?)',(u['id'],b.get('book_id')))
   return self.send(200,{'ok':True})
  return self.send(404,{'error':'Not found'})
if __name__=='__main__':
 from deployment_guard import require_development_server
 require_development_server()
 init();print('LibraAI: http://127.0.0.1:8000');ThreadingHTTPServer(('127.0.0.1',8000),Handler).serve_forever()
