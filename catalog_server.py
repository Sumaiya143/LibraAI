"""Catalog v2: bounded, indexed, paginated discovery API; existing routes retained."""
import os,sqlite3,urllib.parse,time,threading
from http.server import ThreadingHTTPServer
from verified_server import VerifiedHandler
from release_server import install
from server import db

DEFAULT_DISCOVERY_BOOKS = [
 ('Pride and Prejudice','Jane Austen','Classic Fiction','A witty social novel about manners, family, and love.',0),
 ('Jane Eyre','Charlotte Brontë','Classic Fiction','A coming-of-age story of independence, integrity, and belonging.',0),
 ('Wuthering Heights','Emily Brontë','Classic Fiction','A dramatic tale of passion and the consequences of revenge.',0),
 ('Frankenstein','Mary Shelley','Gothic & Horror','A landmark Gothic novel exploring ambition, science, and responsibility.',0),
 ('Dracula','Bram Stoker','Gothic & Horror','A classic Gothic horror story told through letters and journal entries.',0),
 ('The Adventures of Sherlock Holmes','Arthur Conan Doyle','Mystery','Twelve cases featuring the celebrated detective Sherlock Holmes.',0),
 ('The Sign of the Four','Arthur Conan Doyle','Mystery','A Holmes mystery of secrets, treasure, and deduction.',0),
 ('The Count of Monte Cristo','Alexandre Dumas','Adventure','An epic adventure of betrayal, escape, and carefully planned justice.',0),
 ('Twenty Thousand Leagues Under the Seas','Jules Verne','Science Fiction','An imaginative voyage beneath the oceans aboard the Nautilus.',0),
 ('Journey to the Center of the Earth','Jules Verne','Science Fiction','An expedition into a fantastical subterranean world.',0),
 ('The Time Machine','H. G. Wells','Science Fiction','A pioneering time-travel adventure and social thought experiment.',0),
 ('The War of the Worlds','H. G. Wells','Science Fiction','A classic alien-invasion story and portrait of human vulnerability.',0),
 ('The Wonderful Wizard of Oz','L. Frank Baum','Fantasy','A magical journey through Oz with Dorothy and her companions.',0),
 ('Alice’s Adventures in Wonderland','Lewis Carroll','Fantasy','A curious girl discovers a world of playful logic and strange characters.',0),
 ('The Secret Garden','Frances Hodgson Burnett','Children & Young Adult','A neglected garden helps transform the lives of three children.',0),
 ('Little Women','Louisa May Alcott','Children & Young Adult','The March sisters grow through family life, ambition, and change.',0),
 ('The Art of War','Sun Tzu','Philosophy','A concise classical text on strategy, preparation, and leadership.',0),
 ('Meditations','Marcus Aurelius','Philosophy','Personal reflections on discipline, virtue, and Stoic philosophy.',0),
 ('The Republic','Plato','Philosophy','A foundational dialogue about justice, society, and the ideal state.',0),
 ('The Souls of Black Folk','W. E. B. Du Bois','History & Society','A landmark collection of essays on identity, history, and society.',0),
 ('Narrative of the Life of Frederick Douglass','Frederick Douglass','Biography','The influential autobiography of an abolitionist and public speaker.',0),
 ('The Story of My Experiments with Truth','M. K. Gandhi','Biography','An autobiographical account of personal principles and public life.',0),
 ('Walden','Henry David Thoreau','Nature & Travel','Reflections on simple living, nature, and independent thought.',0),
 ('The Call of the Wild','Jack London','Adventure','A dog’s journey into the harsh wilderness of the Yukon.',0),
 ('The Odyssey','Homer','Poetry & Drama','An epic poem following Odysseus on his long journey home.',0),
]

def seed_discovery_books(connection):
    # Starter discovery shelf contains catalog metadata only, not ebook files or reading rights.
    for title, author, category, description, price in DEFAULT_DISCOVERY_BOOKS[:17]:
        connection.execute("""INSERT INTO books(title,author,category,description,price,approved)
            SELECT ?,?,?,?,?,1 WHERE NOT EXISTS
            (SELECT 1 FROM books WHERE title=? AND author=?)""",
            (title, author, category, description, price, title, author))

def migrate():
 install()
 with db() as c:
  seed_discovery_books(c)
  c.execute('CREATE INDEX IF NOT EXISTS idx_books_approved_category ON books(approved,category,id)')
  c.execute('CREATE INDEX IF NOT EXISTS idx_books_author ON books(author)')
  c.execute('CREATE INDEX IF NOT EXISTS idx_reviews_book ON reviews(book_id)')
  c.execute('CREATE TABLE IF NOT EXISTS reading_progress(user_id INTEGER NOT NULL,book_id INTEGER NOT NULL,percent INTEGER NOT NULL CHECK(percent BETWEEN 0 AND 100),updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,book_id))')
  c.execute('CREATE TABLE IF NOT EXISTS wishlists(user_id INTEGER NOT NULL,book_id INTEGER NOT NULL,PRIMARY KEY(user_id,book_id))')
  c.execute('CREATE TABLE IF NOT EXISTS reading_goals(user_id INTEGER PRIMARY KEY,weekly_books INTEGER NOT NULL CHECK(weekly_books BETWEEN 1 AND 50),updated TEXT DEFAULT CURRENT_TIMESTAMP)')
  c.execute('CREATE TABLE IF NOT EXISTS reading_completions(user_id INTEGER NOT NULL,book_id INTEGER NOT NULL,completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,book_id))')

# Process-local login/signup throttling. Deploy behind a trusted reverse proxy
# with a shared rate limiter for multi-worker production environments.
_AUTH_ATTEMPTS = {}
_AUTH_LOCK = threading.Lock()
def auth_throttled(client, route, now=None):
 now = time.monotonic() if now is None else now
 key = (client, route)
 with _AUTH_LOCK:
  if len(_AUTH_ATTEMPTS) > 10000:
   for k, values in list(_AUTH_ATTEMPTS.items()):
    if not values or values[-1] < now-900: _AUTH_ATTEMPTS.pop(k, None)
  attempts = [t for t in _AUTH_ATTEMPTS.get(key, []) if t > now-900]
  if len(attempts) >= 10:
   _AUTH_ATTEMPTS[key] = attempts
   return True
  attempts.append(now)
  _AUTH_ATTEMPTS[key] = attempts
  return False

def persistent_auth_throttled(client, route, now=None, database=None):
 """SQLite-backed sliding-window limiter shared across processes on one database.

 The database write lock makes the count-and-insert atomic, preventing concurrent
 requests from racing past the limit. Do not trust client-supplied forwarding headers.
 """
 now = int(time.time() if now is None else now)
 if route not in ('/api/login', '/api/signup'):
  raise ValueError('Unsupported authentication route')
 if not isinstance(client, str) or not client or len(client) > 128:
  raise ValueError('Invalid client identifier')
 connection = sqlite3.connect(database, timeout=10) if database else db()
 try:
  connection.execute('BEGIN IMMEDIATE')
  connection.execute('CREATE TABLE IF NOT EXISTS auth_rate_events (client TEXT NOT NULL, route TEXT NOT NULL, occurred_at INTEGER NOT NULL)')
  connection.execute('CREATE INDEX IF NOT EXISTS idx_auth_rate_events ON auth_rate_events(client,route,occurred_at)')
  connection.execute('DELETE FROM auth_rate_events WHERE occurred_at<=?', (now-900,))
  count = connection.execute('SELECT COUNT(*) FROM auth_rate_events WHERE client=? AND route=? AND occurred_at>?', (client,route,now-900)).fetchone()[0]
  if count >= 10:
   connection.commit()
   return True
  connection.execute('INSERT INTO auth_rate_events(client,route,occurred_at) VALUES(?,?,?)', (client,route,now))
  connection.commit()
  return False
 except Exception:
  connection.rollback()
  raise
 finally:
  connection.close()

class CatalogHandler(VerifiedHandler):
 def do_GET(self):
  path=urllib.parse.urlparse(self.path).path
  if path=='/api/health/live':
   return self.send(200,{'status':'alive','service':'LibraAI'})
  if path=='/api/health/ready':
   try:
    with db() as c:c.execute('SELECT 1').fetchone()
    return self.send(200,{'status':'ready','database':'reachable'})
   except sqlite3.Error:
    return self.send(503,{'status':'unavailable','database':'unreachable'})
  p=urllib.parse.urlparse(self.path)
  if p.path=='/api/privacy/export':
   u=self.user()
   if not u:return self.send(401,{'error':'Sign in required'})
   tables={'reading_progress':'user_id','reading_goals':'user_id','reading_completions':'user_id','wishlists':'user_id','notes':'user_id','reviews':'user_id','orders':'user_id','library':'user_id'}
   with db() as c:
    payload={'profile':dict(u),'data':{}}
    for table,column in tables.items():
     if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():
      payload['data'][table]=[dict(r) for r in c.execute('SELECT * FROM '+table+' WHERE '+column+'=?',(u['id'],)).fetchall()]
   return self.send(200,payload)
  if p.path in ('/api/reading-progress','/api/wishlist','/api/reading-goals'):
   u=self.user()
   if not u:return self.send(401,{'error':'Sign in required'})
   with db() as c:
    if p.path=='/api/reading-goals':
     goal=c.execute('SELECT weekly_books FROM reading_goals WHERE user_id=?',(u['id'],)).fetchone()
     completed=c.execute('SELECT COUNT(*) FROM reading_progress WHERE user_id=? AND percent=100',(u['id'],)).fetchone()[0]
     weekly=c.execute("SELECT COUNT(*) FROM reading_completions WHERE user_id=? AND completed_at >= datetime('now','weekday 0','-7 days')",(u['id'],)).fetchone()[0]
     target=goal['weekly_books'] if goal else None
     return self.send(200,{'weekly_books':target,'completed_total':completed,'completed_this_week':weekly,'remaining_this_week':max(0,target-weekly) if target else None,'weekly_percent':min(100,round(100*weekly/target)) if target else 0})
    if p.path=='/api/reading-progress':
     rows=c.execute('SELECT p.book_id,b.title,p.percent,p.updated FROM reading_progress p JOIN books b ON b.id=p.book_id WHERE p.user_id=? ORDER BY p.updated DESC',(u['id'],)).fetchall()
    else:
     rows=c.execute('SELECT b.id,b.title,b.author,b.price FROM wishlists w JOIN books b ON b.id=w.book_id WHERE w.user_id=? ORDER BY b.title',(u['id'],)).fetchall()
   return self.send(200,[dict(r) for r in rows])

  if p.path!='/api/catalog/v2':return super().do_GET()
  args=urllib.parse.parse_qs(p.query,keep_blank_values=True)
  try:
   page=int(args.get('page',['1'])[0]);limit=int(args.get('limit',['12'])[0])
   if not (1<=page<=100000 and 1<=limit<=50):raise ValueError()
  except (ValueError,TypeError):return self.send(400,{'error':'page must be >=1 and limit must be 1..50'})
  q=args.get('q',[''])[0].strip()[:120]
  category=args.get('category',[''])[0].strip()[:80]
  sort=args.get('sort',['newest'])[0]
  ordering={'newest':'b.id DESC','oldest':'b.id ASC','title':'b.title COLLATE NOCASE ASC','price_low':'b.price ASC,b.id DESC','price_high':'b.price DESC,b.id DESC','rating':'rating DESC,b.id DESC'}
  if sort not in ordering:return self.send(400,{'error':'Invalid sort'})
  where=['b.approved=1'];params=[]
  if q:
   escaped=q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
   where.append("(b.title LIKE ? ESCAPE '\\' OR b.author LIKE ? ESCAPE '\\' OR b.description LIKE ? ESCAPE '\\')")
   params.extend(['%'+escaped+'%']*3)
  if category:where.append('b.category=?');params.append(category)
  clause=' AND '.join(where)
  with db() as c:
   total=c.execute('SELECT COUNT(*) FROM books b WHERE '+clause,params).fetchone()[0]
   rows=c.execute('''SELECT b.id,b.title,b.author,b.category,b.description,b.price,b.created,
       COALESCE(ROUND(AVG(r.rating),2),0) rating,COUNT(r.id) review_count
       FROM books b LEFT JOIN reviews r ON r.book_id=b.id WHERE '''+clause+
       ' GROUP BY b.id ORDER BY '+ordering[sort]+' LIMIT ? OFFSET ?',params+[limit,(page-1)*limit]).fetchall()
  return self.send(200,{'items':[dict(r) for r in rows],'page':page,'limit':limit,'total':total,'pages':(total+limit-1)//limit})

 def do_POST(self):
  # Reject cross-origin browser writes when Origin is supplied; same-origin requests work.
  origin=self.headers.get('Origin')
  if origin:
   try:
    parsed=urllib.parse.urlparse(origin)
    allowed_host=self.headers.get('Host','')
    if parsed.scheme not in ('http','https') or parsed.netloc!=allowed_host:
     return self.send(403,{'error':'Cross-origin request rejected'})
   except ValueError:return self.send(403,{'error':'Invalid origin'})
  p=urllib.parse.urlparse(self.path).path
  if os.getenv('LIBRAAI_AUTH_THROTTLE','1') == '1' and p in ('/api/login','/api/signup') and persistent_auth_throttled(self.client_address[0],p):
   return self.send(429,{'error':'Too many attempts. Try again later.'})
  if p=='/api/privacy/clear-reading-data':
   u=self.user()
   if not u:return self.send(401,{'error':'Sign in required'})
   data=self.body()
   if not isinstance(data,dict) or data.get('confirmation')!='DELETE MY READING DATA':
    return self.send(400,{'error':'Explicit confirmation required: DELETE MY READING DATA'})
   # Only personal reading data is cleared; purchases, reviews and the account remain intact.
   with db() as c:
    for table in ('reading_progress','reading_completions','reading_goals','wishlists'):
     c.execute('DELETE FROM '+table+' WHERE user_id=?',(u['id'],))
   return self.send(200,{'ok':True,'deleted':['reading_progress','reading_completions','reading_goals','wishlists']})
  if p not in ('/api/reading-progress','/api/wishlist','/api/reading-goals'):return super().do_POST()
  u=self.user()
  if not u:return self.send(401,{'error':'Sign in required'})
  b=self.body()
  if not isinstance(b,dict):return self.send(400,{'error':'JSON object required'})
  if p=='/api/reading-goals':
   value=b.get('weekly_books')
   if isinstance(value,bool) or not (isinstance(value,int) or isinstance(value,str) and value.isdecimal()):return self.send(400,{'error':'weekly_books must be 1..50'})
   try:weekly=int(value)
   except (TypeError,ValueError):return self.send(400,{'error':'weekly_books must be 1..50'})
   if not 1<=weekly<=50:return self.send(400,{'error':'weekly_books must be 1..50'})
   with db() as c:c.execute('INSERT INTO reading_goals(user_id,weekly_books) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET weekly_books=excluded.weekly_books,updated=CURRENT_TIMESTAMP',(u['id'],weekly))
   return self.send(200,{'ok':True,'weekly_books':weekly})
  value=b.get('book_id')
  if isinstance(value,bool) or not (isinstance(value,int) or isinstance(value,str) and value.isdecimal()):return self.send(400,{'error':'Invalid book ID'})
  try:bid=int(value)
  except (TypeError,ValueError):return self.send(400,{'error':'Invalid book ID'})
  if bid<1:return self.send(400,{'error':'Invalid book ID'})
  with db() as c:
   if not c.execute('SELECT 1 FROM books WHERE id=? AND approved=1',(bid,)).fetchone():return self.send(404,{'error':'Book unavailable'})
   if p=='/api/wishlist':
    saved=b.get('saved',True)
    if not isinstance(saved,bool):return self.send(400,{'error':'saved must be a boolean'})
    if saved:c.execute('INSERT OR IGNORE INTO wishlists(user_id,book_id) VALUES(?,?)',(u['id'],bid))
    else:c.execute('DELETE FROM wishlists WHERE user_id=? AND book_id=?',(u['id'],bid))
    return self.send(200,{'ok':True,'saved':saved})
   value=b.get('percent')
   if isinstance(value,bool) or not (isinstance(value,int) or isinstance(value,str) and value.isdecimal()):return self.send(400,{'error':'Percent must be 0..100'})
   try:percent=int(value)
   except (TypeError,ValueError):return self.send(400,{'error':'Percent must be 0..100'})
   if not 0<=percent<=100:return self.send(400,{'error':'Percent must be 0..100'})
   old=c.execute('SELECT percent FROM reading_progress WHERE user_id=? AND book_id=?',(u['id'],bid)).fetchone()
   c.execute('INSERT INTO reading_progress(user_id,book_id,percent) VALUES(?,?,?) ON CONFLICT(user_id,book_id) DO UPDATE SET percent=excluded.percent,updated=CURRENT_TIMESTAMP',(u['id'],bid,percent))
   if percent==100 and (not old or old['percent']<100):
    c.execute('INSERT OR IGNORE INTO reading_completions(user_id,book_id) VALUES(?,?)',(u['id'],bid))
  return self.send(200,{'ok':True,'percent':percent})

if __name__=='__main__':
 from deployment_guard import require_development_server
 require_development_server()
 migrate();port=int(os.getenv('PORT','8000'))
 print('LibraAI catalog upgrade: http://127.0.0.1:'+str(port))
 ThreadingHTTPServer(('127.0.0.1',port),CatalogHandler).serve_forever()
