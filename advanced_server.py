# LibraAI advanced extension
import os,json,sqlite3,time,csv,io,re,hashlib,secrets,urllib.parse
from http.server import ThreadingHTTPServer
from commerce_server import Commerce,setup,db

def upgrade():
 setup()
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS vault(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,book_id INTEGER,chapter TEXT,page TEXT,kind TEXT NOT NULL DEFAULT 'note',body TEXT NOT NULL,updated TEXT DEFAULT CURRENT_TIMESTAMP);CREATE INDEX IF NOT EXISTS idx_vault_user ON vault(user_id);CREATE TABLE IF NOT EXISTS planner(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,task TEXT NOT NULL,due TEXT,minutes INTEGER DEFAULT 25,done INTEGER DEFAULT 0);CREATE INDEX IF NOT EXISTS idx_planner_user ON planner(user_id);CREATE TABLE IF NOT EXISTS sync_items(user_id INTEGER NOT NULL,item_key TEXT NOT NULL,body TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,updated TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,item_key));CREATE TABLE IF NOT EXISTS import_previews(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL,payload TEXT NOT NULL,created INTEGER NOT NULL);CREATE TABLE IF NOT EXISTS workflows(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,name TEXT NOT NULL,trigger_name TEXT NOT NULL,action_name TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 0);CREATE TABLE IF NOT EXISTS workflow_runs(id INTEGER PRIMARY KEY,workflow_id INTEGER NOT NULL,status TEXT NOT NULL,details TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);CREATE TABLE IF NOT EXISTS webhooks(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,url TEXT NOT NULL,secret TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 0);CREATE TABLE IF NOT EXISTS indoor_locations(id INTEGER PRIMARY KEY,branch TEXT NOT NULL,label TEXT NOT NULL,x INTEGER NOT NULL,y INTEGER NOT NULL);CREATE TABLE IF NOT EXISTS pickups(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,book_id INTEGER NOT NULL,token_hash TEXT UNIQUE NOT NULL,status TEXT DEFAULT 'reserved',created TEXT DEFAULT CURRENT_TIMESTAMP);CREATE TABLE IF NOT EXISTS metrics(id INTEGER PRIMARY KEY,path TEXT,latency_ms REAL,code INTEGER,created INTEGER);CREATE INDEX IF NOT EXISTS idx_metrics_created ON metrics(created);''')
  if not c.execute('SELECT 1 FROM indoor_locations LIMIT 1').fetchone():c.executemany('INSERT INTO indoor_locations(branch,label,x,y) VALUES(?,?,?,?,?)'.replace('?,?,?,?,?','?,?,?,?'),[('Main','Entrance',10,80),('Main','Fiction Shelf',40,25),('Main','Study Room',75,25),('Main','Computer Lab',75,75),('Main','Service Desk',30,75)])
class Advanced(Commerce):
 def send(self,status,obj,cookie=None):
  if isinstance(obj,dict) and status>=400:obj.setdefault('ok',False)
  return super().send(status,obj,cookie)
 def _auth(self,roles=None):
  u=self.user()
  if not u:self.send(401,{'error':'Sign in required'});return None
  if roles and u['role'] not in roles:self.send(403,{'error':'Insufficient permissions'});return None
  return u
 def do_GET(self):
  start=time.perf_counter();p=urllib.parse.urlparse(self.path);path=p.path
  try:
   if path=='/api/advanced/health':
    with db() as c:
     count=c.execute('SELECT COUNT(*) FROM books').fetchone()[0]
     metrics=c.execute('SELECT COUNT(*),AVG(latency_ms) FROM metrics WHERE created>?',(int(time.time())-3600,)).fetchone()
    return self.send(200,{'status':'ok','database':'ok','catalog_count':count,'requests_last_hour':metrics[0],'avg_latency_ms':round(metrics[1] or 0,2),'payment_live_verified':False,'external_ai_verified':False})
   if path=='/api/advanced/locations':
    u=self._auth()
    if not u:return
    branch=urllib.parse.parse_qs(p.query).get('branch',['Main'])[0][:80]
    with db() as c:return self.send(200,[dict(r) for r in c.execute('SELECT * FROM indoor_locations WHERE branch=? ORDER BY id',(branch,))])
   if path=='/api/advanced/command':
    u=self._auth()
    if not u:return
    q=urllib.parse.parse_qs(p.query).get('q',[''])[0].lower().strip()[:100]
    commands=[('Books','/','Browse catalog'),('My notes','/advanced-suite.html#vault','Knowledge vault'),('My tasks','/advanced-suite.html#planner','Reading planner'),('Import books','/advanced-suite.html#import','Import preview'),('System health','/advanced-suite.html#health','Health dashboard'),('Indoor map','/advanced-suite.html#map','Indoor navigation'),('Workflows','/advanced-suite.html#workflow','Automation rules')]
    return self.send(200,[{'name':a,'url':b,'description':d} for a,b,d in commands if (a!='Import books' and a!='Workflows' or u['role'] in ('merchant','admin')) and (a!='System health' or u['role']=='admin') and q in (a+' '+d).lower()][:10])
   if path=='/api/advanced/vault':
    u=self._auth()
    if not u:return
    q=urllib.parse.parse_qs(p.query).get('q',[''])[0][:120]
    with db() as c:return self.send(200,[dict(r) for r in c.execute('SELECT * FROM vault WHERE user_id=? AND body LIKE ? ORDER BY id DESC LIMIT 100',(u['id'],'%'+q+'%'))])
   if path=='/api/advanced/planner':
    u=self._auth()
    if not u:return
    with db() as c:return self.send(200,[dict(r) for r in c.execute('SELECT * FROM planner WHERE user_id=? ORDER BY done,due,id',(u['id'],))])
   if path=='/api/advanced/workflows':
    u=self._auth()
    if not u:return
    with db() as c:return self.send(200,[dict(r) for r in c.execute('SELECT id,name,trigger_name,action_name,enabled FROM workflows WHERE user_id=?',(u['id'],))])
   if path=='/api/advanced/privacy/export':
    u=self._auth()
    if not u:return
    with db() as c:
     data={t:[dict(r) for r in c.execute('SELECT * FROM '+t+' WHERE user_id=?',(u['id'],))] for t in ('vault','planner','sync_items','workflows')}
    return self.send(200,data)
   return super().do_GET()
  finally:
   if path.startswith('/api/') and path!='/api/advanced/health':
    try:
     with db() as c:c.execute('INSERT INTO metrics(path,latency_ms,code,created) VALUES(?,?,?,?)',(path,(time.perf_counter()-start)*1000,200,int(time.time())))
    except Exception:pass
 def do_POST(self):
  path=urllib.parse.urlparse(self.path).path
  if not path.startswith('/api/advanced/'):return super().do_POST()
  u=self._auth()
  if not u:return
  b=self.body()
  if not isinstance(b,dict):return self.send(400,{'error':'JSON object required'})
  if path=='/api/advanced/vault':
   body=str(b.get('body','')).strip()[:10000]
   if not body:return self.send(400,{'error':'Note cannot be empty'})
   with db() as c:
    c.execute('INSERT INTO vault(user_id,book_id,chapter,page,kind,body) VALUES(?,?,?,?,?,?)',(u['id'],b.get('book_id'),str(b.get('chapter',''))[:120],str(b.get('page',''))[:40],str(b.get('kind','note'))[:30],body))
   return self.send(201,{'ok':True})
  if path=='/api/advanced/planner':
   task=str(b.get('task','')).strip()[:300]
   if not task:return self.send(400,{'error':'Task required'})
   try:minutes=max(5,min(480,int(b.get('minutes',25))))
   except (TypeError,ValueError):return self.send(400,{'error':'Minutes must be a number'})
   with db() as c:c.execute('INSERT INTO planner(user_id,task,due,minutes) VALUES(?,?,?,?)',(u['id'],task,str(b.get('due',''))[:30],minutes))
   return self.send(201,{'ok':True})
  if path=='/api/advanced/planner/complete':
   with db() as c:r=c.execute('UPDATE planner SET done=1 WHERE id=? AND user_id=?',(b.get('id'),u['id']))
   return self.send(200 if r.rowcount else 404,{'ok':bool(r.rowcount)})
  if path=='/api/advanced/planner/delete':
   with db() as c:r=c.execute('DELETE FROM planner WHERE id=? AND user_id=?',(b.get('id'),u['id']))
   return self.send(200 if r.rowcount else 404,{'ok':bool(r.rowcount)})
  if path=='/api/advanced/sync':
   key=str(b.get('key',''))[:100];body=json.dumps(b.get('data'))
   if not key or len(body)>20000:return self.send(400,{'error':'Invalid sync item'})
   with db() as c:
    r=c.execute('SELECT revision,body FROM sync_items WHERE user_id=? AND item_key=?',(u['id'],key)).fetchone()
    if r and int(b.get('revision',0))!=r['revision']:return self.send(409,{'error':'Sync conflict','server_revision':r['revision'],'server_data':json.loads(r['body'])})
    revision=(r['revision']+1) if r else 1
    c.execute('INSERT INTO sync_items(user_id,item_key,body,revision) VALUES(?,?,?,?) ON CONFLICT(user_id,item_key) DO UPDATE SET body=excluded.body,revision=excluded.revision,updated=CURRENT_TIMESTAMP',(u['id'],key,body,revision))
   return self.send(200,{'ok':True,'revision':revision})
  if path=='/api/advanced/import/preview':
   if u['role'] not in ('merchant','admin'):return self.send(403,{'error':'Merchant role required'})
   data=str(b.get('csv',''))
   if len(data)>500000:return self.send(413,{'error':'CSV too large'})
   rows=list(csv.DictReader(io.StringIO(data)))[:1000];valid=[];issues=[];seen=set()
   with db() as c:existing={(r['title'].lower(),r['author'].lower()) for r in c.execute('SELECT title,author FROM books')}
   for i,row in enumerate(rows,2):
    title=(row.get('title') or '').strip()[:200];author=(row.get('author') or '').strip()[:150];isbn=(row.get('isbn') or '').replace('-','').strip()
    reason=[]
    if not title or not author:reason.append('Missing title or author')
    if isbn and (not isbn.isdigit() or len(isbn) not in (10,13)):reason.append('Invalid ISBN format')
    k=(title.lower(),author.lower())
    if k in seen or k in existing:reason.append('Duplicate title/author')
    seen.add(k)
    if reason:issues.append({'line':i,'title':title,'issues':reason})
    else:valid.append({'title':title,'author':author,'category':(row.get('category') or 'General')[:80]})
   token=secrets.token_urlsafe(20)
   with db() as c:c.execute('INSERT INTO import_previews(token,user_id,payload,created) VALUES(?,?,?,?)',(token,u['id'],json.dumps(valid),int(time.time())))
   return self.send(200,{'token':token,'valid_count':len(valid),'issues':issues,'preview':valid[:15],'notice':'Only title, author, category are imported; ISBN is validated but not stored by legacy schema.'})
  if path=='/api/advanced/import/commit':
   if u['role'] not in ('merchant','admin'):return self.send(403,{'error':'Merchant role required'})
   with db() as c:
    c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT * FROM import_previews WHERE token=? AND user_id=?',(b.get('token'),u['id'])).fetchone()
    if not r or int(time.time())-r['created']>1800:return self.send(400,{'error':'Preview expired or invalid'})
    items=json.loads(r['payload']);c.executemany('INSERT INTO books(title,author,category,merchant_id,approved) VALUES(?,?,?,?,0)',[(x['title'],x['author'],x['category'],u['id']) for x in items]);c.execute('DELETE FROM import_previews WHERE token=?',(b.get('token'),))
   return self.send(201,{'ok':True,'submitted_for_review':len(items)})
  if path=='/api/advanced/workflows':
   if u['role'] not in ('merchant','admin'):return self.send(403,{'error':'Merchant role required'})
   trigger=b.get('trigger');action=b.get('action')
   if trigger not in ('overdue','new_book','reservation') or action not in ('in_app_reminder','notify_staff'):return self.send(400,{'error':'Unsupported trigger/action'})
   with db() as c:c.execute('INSERT INTO workflows(user_id,name,trigger_name,action_name) VALUES(?,?,?,?)',(u['id'],str(b.get('name','Rule'))[:100],trigger,action))
   return self.send(201,{'ok':True,'enabled':False,'notice':'Rules are saved disabled; execution scheduler and notification transport are not configured.'})
  if path=='/api/advanced/verify':
   question=str(b.get('question','')).lower()[:300];u_id=u['id']
   with db() as c:notes=[dict(r) for r in c.execute('SELECT book_id,chapter,page,body FROM vault WHERE user_id=? ORDER BY id DESC LIMIT 300',(u_id,))]
   terms=set(re.findall(r'[a-zA-Z]{4,}',question));ranked=sorted(((len(terms.intersection(set(re.findall(r'[a-zA-Z]{4,}',n['body'].lower())))),n) for n in notes),key=lambda t:t[0],reverse=True)
   passages=[{'book_id':n['book_id'],'chapter':n['chapter'],'page':n['page'],'passage':n['body'][:450]} for score,n in ranked[:3] if score>0]
   return self.send(200,{'answer':'Relevant saved passages found. Review the cited text; this is retrieval, not a verified AI-generated answer.' if passages else 'No supporting evidence found in your saved knowledge vault.','sources':passages,'confidence':'retrieval-only' if passages else 'insufficient-evidence'})
  if path=='/api/advanced/privacy/clear':
   if b.get('confirm')!='DELETE MY VAULT':return self.send(400,{'error':'Confirmation phrase required'})
   with db() as c:c.execute('DELETE FROM vault WHERE user_id=?',(u['id'],))
   return self.send(200,{'ok':True})
  return self.send(404,{'error':'Unknown advanced endpoint'})
if __name__=='__main__':
 upgrade();port=int(os.getenv('PORT','8000'));print('LibraAI advanced http://127.0.0.1:'+str(port));ThreadingHTTPServer(('127.0.0.1',port),Advanced).serve_forever()
