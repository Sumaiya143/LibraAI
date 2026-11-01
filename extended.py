"""Additional locally working LibraAI workflows; external integrations are explicitly excluded."""
from flask import Blueprint, request, session, redirect, flash, jsonify, render_template_string, abort
from datetime import datetime, timedelta
import sqlite3, os, csv, io

bp=Blueprint('extended',__name__,url_prefix='/workspace')
DB=os.environ.get('LIBRAAI_DB_PATH',os.path.join(os.path.dirname(__file__),'libraai.db'))
def conn():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def initialize():
 c=conn(); c.executescript('''
 CREATE TABLE IF NOT EXISTS workspace_records(id INTEGER PRIMARY KEY,category TEXT NOT NULL,owner INTEGER NOT NULL,title TEXT NOT NULL,details TEXT DEFAULT '',status TEXT DEFAULT 'Open',created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS workspace_memberships(id INTEGER PRIMARY KEY,user_id INTEGER,club_id INTEGER,UNIQUE(user_id,club_id));
 CREATE TABLE IF NOT EXISTS workspace_reservations(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,created TEXT,status TEXT DEFAULT 'Waiting',UNIQUE(user_id,book_id));
 CREATE TABLE IF NOT EXISTS workspace_room_bookings(id INTEGER PRIMARY KEY,room_id INTEGER,user_id INTEGER,day TEXT,slot TEXT,UNIQUE(room_id,day,slot));
 CREATE TABLE IF NOT EXISTS workspace_subscriptions(user_id INTEGER PRIMARY KEY,plan TEXT,updated TEXT);
 CREATE TABLE IF NOT EXISTS workspace_settings(user_id INTEGER PRIMARY KEY,language TEXT DEFAULT 'English',theme TEXT DEFAULT 'Light',font_size INTEGER DEFAULT 18,private_profile INTEGER DEFAULT 1);
 CREATE TABLE IF NOT EXISTS workspace_quizzes(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,question TEXT,answer TEXT,created TEXT);
 CREATE TABLE IF NOT EXISTS workspace_inventory(id INTEGER PRIMARY KEY,book_id INTEGER,delta INTEGER,reason TEXT,actor INTEGER,created TEXT);
 CREATE TABLE IF NOT EXISTS workspace_coupons(code TEXT PRIMARY KEY,discount_percent INTEGER CHECK(discount_percent BETWEEN 0 AND 100),active INTEGER DEFAULT 1);
 CREATE TABLE IF NOT EXISTS workspace_notifications(id INTEGER PRIMARY KEY,user_id INTEGER,body TEXT,created TEXT,seen INTEGER DEFAULT 0);
 CREATE TABLE IF NOT EXISTS workspace_reading_events(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,seconds INTEGER,created TEXT);
 '''); c.execute("INSERT OR IGNORE INTO workspace_coupons VALUES ('READ10',10,1)"); c.commit(); c.close()

CATEGORIES={
 'lists':'Shared reading lists','goals':'Group reading goals','events':'Events and author Q&A','live':'Live reading room schedules','discussions':'Discussion rooms','study':'Study plans','vocabulary':'Vocabulary notebook','quotes':'Favorite quotations','archive':'Digital archive metadata','preservation':'Rare-book preservation records','donations':'Book donation matching','acquisitions':'Acquisitions requests','suppliers':'Supplier contacts','disputes':'Marketplace disputes','gifts':'Book gifts','licensing':'Publisher rights and licensing','royalties':'Royalty ledger entries','alerts':'Alerts and reminders','interlibrary':'Inter-library loan requests','damage':'Lost/damaged reports','audits':'Stock audit records','refunds':'Refund requests','shipments':'Delivery tracking updates','subscriptions':'Subscription requests','purchases':'Purchase requests','scans':'ISBN/barcode scan entries','research':'Research notes','citations':'Citation records','flashcards':'Study flashcard sets','quizzes':'Quiz question bank','translations':'Translation notes','glossary':'Dictionary entries','automation':'Workflow rule proposals','kiosk':'Self-service kiosk transactions','resale':'Second-hand sale inquiries','branches':'Library branch records','publishers':'Publisher submissions','rooms':'Study-room requests'
}
ADMIN={'archive','preservation','acquisitions','suppliers','licensing','royalties','damage','audits','automation','branches','publishers'}

def user():
 uid=session.get('uid')
 if not uid:return None
 c=conn(); row=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone(); c.close(); return row

def esc(s):
 from markupsafe import escape
 return escape(str(s))

def frame(title,content):
 from app import page
 return page(title,content)

@bp.route('/')
def index():
 if not user():return redirect('/login')
 links=''.join(f'<a class="pill" style="display:inline-block;margin:5px;padding:10px" href="/workspace/{k}">{esc(v)}</a>' for k,v in CATEGORIES.items())
 return frame('Workspace','<h1>LibraAI · Extended Workspace</h1><p>Operational local workflows for the complete product suite. External payment, licensed media, live conferencing and third-party AI services are not simulated as real services.</p><div class="card">'+links+'</div><p><a class="btn" href="/workspace/rooms-booking">Book a study room</a> <a class="btn" href="/workspace/reservations">Reserve a book</a> <a class="btn" href="/workspace/preferences">Preferences</a> <a class="btn" href="/workspace/plan">Membership plan</a></p>')

@bp.route('/<category>',methods=['GET','POST'])
def records(category):
 u=user()
 if not u:return redirect('/login')
 if category not in CATEGORIES:abort(404)
 if category in ADMIN and u['role']!='admin':abort(403)
 c=conn()
 if request.method=='POST':
  title=request.form.get('title','').strip()[:160]; details=request.form.get('details','').strip()[:4000]
  if not title:flash('Title is required')
  else:
   c.execute('INSERT INTO workspace_records(category,owner,title,details,status,created) VALUES(?,?,?,?,?,?)',(category,u['id'],title,details,'Open',datetime.utcnow().isoformat()));c.commit()
   c.close();return redirect('/workspace/'+category)
 rows=c.execute('SELECT r.*,u.name FROM workspace_records r JOIN users u ON u.id=r.owner WHERE category=? AND (owner=? OR ?=1) ORDER BY r.id DESC LIMIT 200',(category,u['id'],int(u['role']=='admin'))).fetchall();c.close()
 items=''.join(f'<div class="card" style="margin:12px 0"><b>{esc(r["title"])}</b> <span class="pill">{esc(r["status"])}</span><p>{esc(r["details"])}</p><small>{esc(r["created"])}</small><form method="post" action="/workspace/item/{r["id"]}/close"><button class="btn">Mark resolved</button></form></div>' for r in rows)
 html=f'<h1>{esc(CATEGORIES[category])}</h1><p><a href="/workspace/">← All workflows</a></p><div class="card"><form method="post"><label>Title</label><input class="input" maxlength="160" name="title" required><label>Details</label><textarea class="input" name="details" rows="4"></textarea><button class="btn">Create record</button></form></div><h2>Saved records</h2>{items or "<p>No records yet.</p>"}'
 return frame(CATEGORIES[category],html)

@bp.post('/item/<int:rid>/close')
def close(rid):
 u=user()
 if not u:return redirect('/login')
 c=conn();r=c.execute('SELECT * FROM workspace_records WHERE id=?',(rid,)).fetchone()
 if not r:abort(404)
 if r['owner']!=u['id'] and u['role']!='admin':abort(403)
 c.execute("UPDATE workspace_records SET status='Resolved' WHERE id=?",(rid,));c.commit();c.close()
 return redirect('/workspace/'+r['category'])

@bp.route('/rooms-booking',methods=['GET','POST'])
def room_booking():
 u=user()
 if not u:return redirect('/login')
 c=conn()
 if request.method=='POST':
  rid=request.form.get('room_id',type=int);day=request.form.get('day','');slot=request.form.get('slot','')
  if day<datetime.now().date().isoformat() or slot not in ['09:00','11:00','13:00','15:00','17:00'] or not c.execute('SELECT 1 FROM rooms WHERE id=?',(rid,)).fetchone():flash('Invalid room, date or slot')
  else:
   try:c.execute('INSERT INTO workspace_room_bookings(room_id,user_id,day,slot) VALUES(?,?,?,?)',(rid,u['id'],day,slot));c.commit();flash('Room booked')
   except sqlite3.IntegrityError:flash('This time slot is already booked')
 rooms=c.execute('SELECT * FROM rooms').fetchall();mine=c.execute('SELECT b.*,r.name FROM workspace_room_bookings b JOIN rooms r ON r.id=b.room_id WHERE user_id=? ORDER BY day DESC',(u['id'],)).fetchall();c.close()
 opts=''.join(f'<option value="{r["id"]}">{esc(r["name"])} — {esc(r["branch"])}</option>' for r in rooms)
 booked=''.join(f'<p>{esc(x["name"])} — {esc(x["day"])} {esc(x["slot"])}</p>' for x in mine)
 return frame('Room booking',f'<h1>Study-room reservations</h1><div class="card"><form method="post"><select class="input" name="room_id">{opts}</select><input class="input" type="date" name="day" required min="{datetime.now().date().isoformat()}"><select class="input" name="slot">'+''.join(f'<option>{x}</option>' for x in ['09:00','11:00','13:00','15:00','17:00'])+f'</select><button class="btn">Book room</button></form></div><h2>My bookings</h2>{booked}')

@bp.route('/reservations',methods=['GET','POST'])
def reservations():
 u=user()
 if not u:return redirect('/login')
 c=conn()
 if request.method=='POST':
  bid=request.form.get('book_id',type=int)
  if c.execute('SELECT 1 FROM books WHERE id=?',(bid,)).fetchone():c.execute('INSERT OR IGNORE INTO workspace_reservations(user_id,book_id,created) VALUES(?,?,?)',(u['id'],bid,datetime.utcnow().isoformat()));c.commit()
 books=c.execute('SELECT id,title FROM books').fetchall();rows=c.execute('SELECT b.title,r.status FROM workspace_reservations r JOIN books b ON b.id=r.book_id WHERE r.user_id=?',(u['id'],)).fetchall();c.close()
 options=''.join(f'<option value="{b["id"]}">{esc(b["title"])}</option>' for b in books)
 return frame('Reservations',f'<h1>Book reservations and waitlist</h1><div class="card"><form method="post"><select name="book_id" class="input">{options}</select><button class="btn">Join waitlist</button></form></div>'+''.join(f'<p>{esc(r["title"])} — {esc(r["status"])}</p>' for r in rows))

@bp.route('/plan',methods=['GET','POST'])
def plan():
 u=user()
 if not u:return redirect('/login')
 c=conn()
 if request.method=='POST':
  p=request.form.get('plan')
  if p in ['Free','Student','Family','Institutional']:
   c.execute('INSERT INTO workspace_subscriptions VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET plan=excluded.plan,updated=excluded.updated',(u['id'],p,datetime.utcnow().isoformat()));c.commit()
 row=c.execute('SELECT plan FROM workspace_subscriptions WHERE user_id=?',(u['id'],)).fetchone();c.close()
 return frame('Membership','<h1>Membership plans</h1><p>Plan selection is recorded locally. This does not charge a card or activate paid provider entitlements.</p><div class="card"><form method="post"><select class="input" name="plan">'+''.join(f'<option>{x}</option>' for x in ['Free','Student','Family','Institutional'])+'</select><button class="btn">Save plan preference</button></form></div><p>Selected: '+esc(row['plan'] if row else 'Free')+'</p>')

@bp.route('/preferences',methods=['GET','POST'])
def preferences():
 u=user()
 if not u:return redirect('/login')
 c=conn()
 if request.method=='POST':
  lang=request.form.get('language');theme=request.form.get('theme');size=request.form.get('font_size',type=int)
  if lang in ['English','Bangla'] and theme in ['Light','Dark','Sepia'] and size and 12<=size<=32:
   c.execute('INSERT INTO workspace_settings(user_id,language,theme,font_size) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET language=excluded.language,theme=excluded.theme,font_size=excluded.font_size',(u['id'],lang,theme,size));c.commit()
 row=c.execute('SELECT * FROM workspace_settings WHERE user_id=?',(u['id'],)).fetchone();c.close()
 return frame('Preferences','<h1>Reading and privacy preferences</h1><div class="card"><form method="post"><label>Language</label><select class="input" name="language"><option>English</option><option>Bangla</option></select><label>Theme</label><select class="input" name="theme"><option>Light</option><option>Dark</option><option>Sepia</option></select><label>Reader font size</label><input class="input" type="number" min="12" max="32" name="font_size" value="18"><button class="btn">Save preferences</button></form></div><p>Stored settings: '+esc(dict(row) if row else 'Default')+'</p>')

@bp.get('/api/records/<category>')
def api_records(category):
 u=user()
 if not u:return jsonify({'error':'Authentication required'}),401
 if category not in CATEGORIES:return jsonify({'error':'Not found'}),404
 c=conn();rows=[dict(r) for r in c.execute('SELECT * FROM workspace_records WHERE category=? AND owner=?',(category,u['id']))];c.close();return jsonify(rows)
