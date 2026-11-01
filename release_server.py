"""Additional functional modules; not a certified production release."""
import os, json, time, secrets, hashlib, sqlite3, urllib.parse, shutil
from pathlib import Path
from http.server import ThreadingHTTPServer
from advanced_server import Advanced,upgrade,db

def install():
 upgrade()
 with db() as c:
  c.executescript("""CREATE TABLE IF NOT EXISTS environmental_readings(id INTEGER PRIMARY KEY,branch TEXT NOT NULL,temperature REAL,humidity REAL,occupancy INTEGER,light_lux REAL,created INTEGER NOT NULL);CREATE TABLE IF NOT EXISTS integration_events(id INTEGER PRIMARY KEY,event_type TEXT NOT NULL,payload TEXT NOT NULL,created INTEGER NOT NULL);CREATE TABLE IF NOT EXISTS user_preferences(user_id INTEGER PRIMARY KEY,retain_history INTEGER NOT NULL DEFAULT 0,personalize INTEGER NOT NULL DEFAULT 0);CREATE TABLE IF NOT EXISTS notification_queue(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,body TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'unread',created INTEGER NOT NULL);CREATE INDEX IF NOT EXISTS idx_notification_user ON notification_queue(user_id,status);""")

class Release(Advanced):
 def do_GET(self):
  p=urllib.parse.urlparse(self.path);path=p.path
  if path=='/api/extra/sync':
   u=self._auth()
   if not u:return
   with db() as c:items=[dict(r) for r in c.execute('SELECT item_key,body,revision,updated FROM sync_items WHERE user_id=?',(u['id'],))]
   return self.send(200,{'items':[dict(x,key=x.pop('item_key'),data=json.loads(x.pop('body'))) for x in items]})
  if path=='/api/extra/notifications':
   u=self._auth()
   if not u:return
   with db() as c:items=[dict(r) for r in c.execute('SELECT id,body,status,created FROM notification_queue WHERE user_id=? ORDER BY id DESC LIMIT 100',(u['id'],))]
   return self.send(200,items)
  if path=='/api/extra/environment':
   u=self._auth()
   if not u:return
   with db() as c:items=[dict(r) for r in c.execute('SELECT * FROM environmental_readings ORDER BY id DESC LIMIT 50')]
   return self.send(200,items)
  if path=='/api/extra/pickups':
   u=self._auth()
   if not u:return
   with db() as c:items=[dict(r) for r in c.execute('SELECT id,book_id,status,created FROM pickups WHERE user_id=? ORDER BY id DESC',(u['id'],))]
   return self.send(200,items)
  if path=='/api/extra/workflow-runs':
   u=self._auth(['merchant','admin'])
   if not u:return
   with db() as c:items=[dict(r) for r in c.execute('SELECT workflow_runs.* FROM workflow_runs JOIN workflows ON workflows.id=workflow_runs.workflow_id WHERE workflows.user_id=? ORDER BY workflow_runs.id DESC LIMIT 100',(u['id'],))]
   return self.send(200,items)
  if path=='/api/extra/privacy':
   u=self._auth()
   if not u:return
   with db() as c:r=c.execute('SELECT retain_history,personalize FROM user_preferences WHERE user_id=?',(u['id'],)).fetchone()
   return self.send(200,dict(r) if r else {'retain_history':0,'personalize':0})
  return super().do_GET()
 def do_POST(self):
  path=urllib.parse.urlparse(self.path).path
  if not path.startswith('/api/extra/'):return super().do_POST()
  u=self._auth()
  if not u:return
  b=self.body()
  if not isinstance(b,dict):return self.send(400,{'error':'JSON object required'})
  if path=='/api/extra/pickup/reserve':
   try:bid=int(b.get('book_id'))
   except:return self.send(400,{'error':'Invalid book'})
   with db() as c:
    book=c.execute('SELECT id FROM books WHERE id=? AND approved=1',(bid,)).fetchone()
    if not book:return self.send(404,{'error':'Book unavailable'})
    token=secrets.token_urlsafe(24)
    c.execute('INSERT INTO pickups(user_id,book_id,token_hash) VALUES(?,?,?)',(u['id'],bid,hashlib.sha256(token.encode()).hexdigest()))
    rid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
   return self.send(201,{'pickup_id':rid,'pickup_code':token,'status':'reserved','notice':'Show code at staffed counter; no physical stock lock is performed.'})
  if path=='/api/extra/pickup/redeem':
   if u['role'] not in ('merchant','admin'):return self.send(403,{'error':'Staff access required'})
   token=str(b.get('pickup_code',''))
   if len(token)>200 or not token:return self.send(400,{'error':'Invalid pickup code'})
   digest=hashlib.sha256(token.encode()).hexdigest()
   with db() as c:
    c.execute('BEGIN IMMEDIATE')
    row=c.execute('SELECT id FROM pickups WHERE token_hash=? AND status=?',(digest,'reserved')).fetchone()
    if not row:return self.send(409,{'error':'Unknown or already redeemed code'})
    c.execute('UPDATE pickups SET status=? WHERE id=?',('collected',row['id']))
   return self.send(200,{'ok':True,'pickup_id':row['id'],'status':'collected'})
  if path=='/api/extra/environment':
   if u['role'] not in ('merchant','admin'):return self.send(403,{'error':'Staff access required'})
   try:
    temp=float(b['temperature']);humidity=float(b['humidity']);occupancy=int(b.get('occupancy',0));light=float(b.get('light_lux',0))
    if not (-30<=temp<=80 and 0<=humidity<=100 and 0<=occupancy<=100000 and 0<=light<=200000):raise ValueError()
   except (ValueError,TypeError,KeyError):return self.send(400,{'error':'Invalid sensor reading'})
   branch=str(b.get('branch','Main'))[:80]
   with db() as c:c.execute('INSERT INTO environmental_readings(branch,temperature,humidity,occupancy,light_lux,created) VALUES(?,?,?,?,?,?)',(branch,temp,humidity,occupancy,light,int(time.time())))
   return self.send(201,{'ok':True,'alerts':(['Humidity out of preferred range'] if humidity>65 or humidity<30 else [])+(['Temperature out of preferred range'] if temp>28 or temp<16 else []),'source':'manual-or-external-ingest; no hardware integration verified'})
  if path=='/api/extra/workflows/enable':
   if u['role'] not in ('merchant','admin'):return self.send(403,{'error':'Staff access required'})
   try:wid=int(b['id'])
   except:return self.send(400,{'error':'Invalid workflow'})
   with db() as c:r=c.execute('UPDATE workflows SET enabled=? WHERE id=? AND user_id=?',(int(bool(b.get('enabled'))),wid,u['id']))
   return self.send(200,{'ok':bool(r.rowcount)})
  if path=='/api/extra/workflows/run':
   if u['role'] not in ('merchant','admin'):return self.send(403,{'error':'Staff access required'})
   try:wid=int(b['id'])
   except:return self.send(400,{'error':'Invalid workflow'})
   with db() as c:
    c.execute('BEGIN IMMEDIATE');rule=c.execute('SELECT * FROM workflows WHERE id=? AND user_id=? AND enabled=1',(wid,u['id'])).fetchone()
    if not rule:return self.send(404,{'error':'Enabled workflow not found'})
    # A controlled test trigger, not a background scheduler or real overdue detector.
    message='Workflow test: '+rule['name']+' / '+rule['trigger_name']+' / '+rule['action_name']
    c.execute('INSERT INTO notification_queue(user_id,body,created) VALUES(?,?,?)',(u['id'],message,int(time.time())))
    c.execute('INSERT INTO workflow_runs(workflow_id,status,details) VALUES(?,?,?)',(wid,'test-completed',message))
   return self.send(200,{'ok':True,'mode':'manual-test','notice':'No automatic event listener or scheduled execution'})
  if path=='/api/extra/privacy':
   with db() as c:c.execute('INSERT INTO user_preferences(user_id,retain_history,personalize) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET retain_history=excluded.retain_history,personalize=excluded.personalize',(u['id'],int(bool(b.get('retain_history'))),int(bool(b.get('personalize')))))
   return self.send(200,{'ok':True})
  if path=='/api/extra/backup':
   if u['role']!='admin':return self.send(403,{'error':'Admin access required'})
   import server
   backup=Path(__file__).parent/'backups';backup.mkdir(exist_ok=True)
   filename=backup/('libra-'+time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)+'.sqlite3')
   with db() as source,sqlite3.connect(filename) as target:source.backup(target)
   with sqlite3.connect(filename) as check:integrity=check.execute('PRAGMA integrity_check').fetchone()[0]
   return self.send(201,{'ok':integrity=='ok','backup_filename':filename.name,'integrity':integrity,'notice':'Manual local backup; automated offsite backups and restore drills are not configured'})
  return self.send(404,{'error':'Unknown endpoint'})

if __name__=='__main__':
 install();from scheduler import start_maintenance;start_maintenance();port=int(os.getenv('PORT','8000'));print('LibraAI functional expansion http://127.0.0.1:'+str(port));ThreadingHTTPServer(('127.0.0.1',port),Release).serve_forever()
