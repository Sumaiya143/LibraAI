"""Saved catalog searches, in-app alerts, and reading streaks (local SQLite)."""
import sqlite3
from datetime import date, timedelta, datetime, timezone
from flask import Blueprint, request, redirect, abort, jsonify
from markupsafe import escape

engagement = Blueprint('engagement', __name__)

def database():
    from app import db
    return db()

def identity():
    from app import current_user
    u=current_user()
    if not u: abort(401)
    return u['id']

def setup():
    with database() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS saved_searches (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, phrase TEXT NOT NULL, genre TEXT NOT NULL DEFAULT '', created TEXT NOT NULL, UNIQUE(user_id,phrase,genre));
        CREATE TABLE IF NOT EXISTS inbox_alerts (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, subject TEXT NOT NULL, message TEXT NOT NULL, read_at TEXT, created TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_alerts_user ON inbox_alerts(user_id,read_at,created);
        CREATE TABLE IF NOT EXISTS search_matches (search_id INTEGER NOT NULL, book_id INTEGER NOT NULL, PRIMARY KEY(search_id,book_id));
        ''')

def matches(book, phrase, genre):
    text=' '.join(str(book.get(k) or '') for k in ('title','author','description','isbn')).casefold()
    return phrase.casefold() in text and (not genre or genre.casefold()==str(book.get('genre') or '').casefold())

def new_book_alerts(book_id):
    """Invoke after an authorized catalog insertion. Idempotent per search/book."""
    with database() as c:
        row=c.execute('SELECT id,title,author,description,isbn,genre FROM books WHERE id=?',(book_id,)).fetchone()
        if row is None: return 0
        book=dict(row); count=0
        for saved in c.execute('SELECT id,user_id,phrase,genre FROM saved_searches').fetchall():
            if not matches(book,saved['phrase'],saved['genre']): continue
            cur=c.execute('INSERT OR IGNORE INTO search_matches(search_id,book_id) VALUES(?,?)',(saved['id'],book_id))
            if cur.rowcount:
                c.execute('INSERT INTO inbox_alerts(user_id,subject,message,created) VALUES(?,?,?,?)',(saved['user_id'],'Book matching your saved search',f'{book["title"]} by {book["author"]}',datetime.now(timezone.utc).isoformat()))
                count+=1
        return count

@engagement.route('/my-alerts',methods=['GET'])
def inbox():
    from app import page
    uid=identity()
    with database() as c:
        searches=c.execute('SELECT * FROM saved_searches WHERE user_id=? ORDER BY id DESC',(uid,)).fetchall()
        alerts=c.execute('SELECT * FROM inbox_alerts WHERE user_id=? ORDER BY id DESC LIMIT 100',(uid,)).fetchall()
        streak=reading_streak(c,uid)
    items=''.join(f'<div class="card"><b>{escape(x["subject"])}</b><p>{escape(x["message"])}</p><small>{escape(x["created"][:16])}</small>'+(' <span class="pill">New</span>' if not x['read_at'] else '')+f'<form method="post" action="/my-alerts/{x["id"]}/read"><button class="btn">Mark read</button></form></div>' for x in alerts)
    searches_html=''.join(f'<div class="card">{escape(x["phrase"])} · {escape(x["genre"] or "All genres")}<form method="post" action="/saved-searches/{x["id"]}/delete"><button class="btn">Remove</button></form></div>' for x in searches)
    body=f'''<h1>Reading alerts & saved searches</h1><p class="muted">Current reading streak: <b>{streak} days</b>. Alerts are generated when the catalog is updated through supported workflows.</p><div class="card"><h2>Save a book search</h2><form method="post" action="/saved-searches"><input class="input" name="phrase" maxlength="120" required placeholder="Title, author or ISBN"><input class="input" name="genre" maxlength="60" placeholder="Optional exact genre"><button class="btn">Save search</button></form></div><h2>Saved searches</h2><div class="grid">{searches_html or '<p>No saved searches.</p>'}</div><h2>Inbox</h2><div class="grid">{items or '<p>No notifications yet.</p>'}</div>'''
    return page('My alerts',body)

@engagement.post('/saved-searches')
def save_search():
    uid=identity(); phrase=request.form.get('phrase','').strip(); genre=request.form.get('genre','').strip()
    if not 2<=len(phrase)<=120 or len(genre)>60: abort(400)
    with database() as c:
        c.execute('INSERT OR IGNORE INTO saved_searches(user_id,phrase,genre,created) VALUES(?,?,?,?)',(uid,phrase,genre,datetime.now(timezone.utc).isoformat()))
    return redirect('/my-alerts')

@engagement.post('/saved-searches/<int:sid>/delete')
def delete_search(sid):
    uid=identity()
    with database() as c:
        c.execute('DELETE FROM search_matches WHERE search_id IN (SELECT id FROM saved_searches WHERE id=? AND user_id=?)',(sid,uid))
        c.execute('DELETE FROM saved_searches WHERE id=? AND user_id=?',(sid,uid))
    return redirect('/my-alerts')

@engagement.post('/my-alerts/<int:aid>/read')
def mark_read(aid):
    uid=identity()
    with database() as c:
        cur=c.execute('UPDATE inbox_alerts SET read_at=? WHERE id=? AND user_id=?',(datetime.now(timezone.utc).isoformat(),aid,uid))
        if not cur.rowcount: abort(404)
    return redirect('/my-alerts')

def reading_streak(c,uid,today=None):
    today=today or date.today()
    try:
        rows=c.execute('SELECT DISTINCT substr(created,1,10) AS day FROM reading_sessions WHERE user_id=? AND minutes>0',(uid,)).fetchall()
    except sqlite3.OperationalError:
        return 0
    days={x['day'] for x in rows}
    current=today if today.isoformat() in days else today-timedelta(days=1)
    streak=0
    while current.isoformat() in days:
        streak+=1;current-=timedelta(days=1)
    return streak

@engagement.get('/api/me/engagement')
def engagement_api():
    uid=identity()
    with database() as c:
        searches=c.execute('SELECT COUNT(*) FROM saved_searches WHERE user_id=?',(uid,)).fetchone()[0]
        unread=c.execute('SELECT COUNT(*) FROM inbox_alerts WHERE user_id=? AND read_at IS NULL',(uid,)).fetchone()[0]
        streak=reading_streak(c,uid)
    return jsonify(saved_searches=searches,unread_alerts=unread,reading_streak_days=streak)
