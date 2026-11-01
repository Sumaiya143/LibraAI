"""Additional self-contained LibraAI functionality, no external credentials required."""
import csv, io, json, sqlite3
from datetime import datetime, timedelta
from flask import Blueprint, request, redirect, Response, jsonify, session, abort

plus = Blueprint('platform_plus', __name__)

def conn():
    from app import db
    return db()

def who():
    from app import current_user
    return current_user()

def setup():
    c=conn()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS reading_events(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,book_id INTEGER NOT NULL,event_type TEXT NOT NULL,seconds INTEGER DEFAULT 0,created TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_events_book_date ON reading_events(book_id,created);
    CREATE TABLE IF NOT EXISTS privacy_preferences(user_id INTEGER PRIMARY KEY,public_activity INTEGER NOT NULL DEFAULT 0,marketing INTEGER NOT NULL DEFAULT 0,language TEXT NOT NULL DEFAULT 'en');
    CREATE TABLE IF NOT EXISTS reading_sessions(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,book_id INTEGER NOT NULL,minutes INTEGER NOT NULL,created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS user_notifications(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,message TEXT NOT NULL,seen INTEGER DEFAULT 0,created TEXT NOT NULL);
    ''')
    c.commit();c.close()

def require():
    u=who()
    if not u: abort(401)
    return u

@plus.post('/api/reading-session')
def reading_session():
    u=require(); data=request.get_json(silent=True) or {}; book_id=data.get('book_id'); minutes=data.get('minutes')
    if not isinstance(book_id,int) or not isinstance(minutes,int) or not 1<=minutes<=240: return jsonify(error='Invalid book or minutes'),400
    c=conn()
    if not c.execute('SELECT 1 FROM books WHERE id=?',(book_id,)).fetchone():c.close();abort(404)
    now=datetime.utcnow().isoformat()
    c.execute('INSERT INTO reading_sessions(user_id,book_id,minutes,created) VALUES(?,?,?,?)',(u['id'],book_id,minutes,now))
    c.execute('INSERT INTO reading_events(user_id,book_id,event_type,seconds,created) VALUES(?,?,?,?,?)',(u['id'],book_id,'read',minutes*60,now))
    c.commit();c.close()
    return jsonify(ok=True,minutes=minutes)

@plus.get('/api/reading-trends')
def trends():
    c=conn(); start=(datetime.utcnow()-timedelta(days=30)).isoformat()
    rows=c.execute('''SELECT b.id,b.title,COUNT(DISTINCT e.user_id) readers,COALESCE(SUM(e.seconds),0) seconds FROM books b LEFT JOIN reading_events e ON e.book_id=b.id AND e.created>=? GROUP BY b.id ORDER BY readers DESC,seconds DESC LIMIT 20''',(start,)).fetchall()
    c.close();return jsonify(books=[dict(x) for x in rows],metric='unique active readers in past 30 days; demo events, not fraud resistant')

@plus.route('/privacy',methods=['GET','POST'])
def privacy():
    from app import page
    u=require(); c=conn()
    if request.method=='POST':
        lang=request.form.get('language','en')
        if lang not in ('en','bn'): c.close();abort(400)
        c.execute('INSERT INTO privacy_preferences(user_id,public_activity,marketing,language) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET public_activity=excluded.public_activity,marketing=excluded.marketing,language=excluded.language',(u['id'],int('public_activity' in request.form),int('marketing' in request.form),lang))
        c.commit()
    pref=c.execute('SELECT * FROM privacy_preferences WHERE user_id=?',(u['id'],)).fetchone();c.close()
    return page('Privacy & preferences','''<h1>Privacy & preferences</h1><p class="muted">Your preferences are stored privately in your account.</p><form method="post" class="card"><label><input type="checkbox" name="public_activity" {% if pref and pref.public_activity %}checked{% endif %}> Show my reading activity publicly</label><p><label><input type="checkbox" name="marketing" {% if pref and pref.marketing %}checked{% endif %}> Receive promotional messages</label></p><label>Preferred language</label><select name="language"><option value="en">English</option><option value="bn" {% if pref and pref.language=='bn' %}selected{% endif %}>বাংলা</option></select><p><button class="btn">Save preferences</button></p></form><p><a class="btn ghost" href="/export/my-data">Export my account data (JSON)</a></p>''',pref=pref)

@plus.get('/export/my-data')
def export_data():
    u=require();c=conn();data={'account':{'name':u['name'],'email':u['email'],'role':u['role']}}
    for table in ('progress','annotations','reviews','wishlist','cart','loans','orders','flashcards','reading_sessions','privacy_preferences'):
        data[table]=[dict(x) for x in c.execute(f'SELECT * FROM {table} WHERE user_id=?',(u['id'],))]
    c.close();return Response(json.dumps(data,indent=2,default=str),mimetype='application/json',headers={'Content-Disposition':'attachment; filename=libraai-my-data.json'})

@plus.get('/admin/export-catalog.csv')
def catalog_csv():
    u=require()
    if u['role']!='admin':abort(403)
    c=conn();rows=c.execute('SELECT id,title,author,genre,isbn,stock,branch,shelf FROM books').fetchall();c.close()
    output=io.StringIO();w=csv.writer(output);w.writerow(['id','title','author','genre','isbn','stock','branch','shelf']);w.writerows([tuple(x) for x in rows])
    return Response(output.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=libraai-catalog.csv'})
