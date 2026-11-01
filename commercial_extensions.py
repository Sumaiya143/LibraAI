"""Additive operational workflows; preserves every existing route and template."""
import csv, io, json, os, sqlite3
from datetime import datetime, timezone
from flask import Blueprint, abort, request, jsonify, session, redirect

commercial = Blueprint('commercial_extensions', __name__)

def database():
    from app import db
    return db()

def account():
    from app import current_user
    u=current_user()
    if u is None: abort(401)
    return u

def admin():
    u=account()
    if u['role']!='admin': abort(403)
    return u

def setup():
    c=database()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS support_tickets(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,subject TEXT NOT NULL,message TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS user_book_lists(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,name TEXT NOT NULL,created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS user_book_list_items(list_id INTEGER NOT NULL,book_id INTEGER NOT NULL,PRIMARY KEY(list_id,book_id));
    CREATE TABLE IF NOT EXISTS book_stock_movements(id INTEGER PRIMARY KEY,book_id INTEGER NOT NULL,delta INTEGER NOT NULL,reason TEXT NOT NULL,actor_id INTEGER NOT NULL,created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS api_idempotency(key TEXT PRIMARY KEY,user_id INTEGER NOT NULL,created TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_support_user ON support_tickets(user_id);
    CREATE INDEX IF NOT EXISTS idx_lists_user ON user_book_lists(user_id);
    ''')
    c.commit();c.close()

def now():return datetime.now(timezone.utc).isoformat()

def payload():
    obj=request.get_json(silent=True)
    if not isinstance(obj,dict): abort(400,'Expected JSON object')
    return obj

def required_text(value,limit):
    if not isinstance(value,str) or not value.strip() or len(value.strip())>limit:abort(400,'Invalid text field')
    return value.strip()

@commercial.route('/api/support',methods=['GET','POST'])
def support():
    u=account();c=database()
    if request.method=='POST':
        data=payload();subject=required_text(data.get('subject'),120);message=required_text(data.get('message'),3000)
        c.execute('INSERT INTO support_tickets(user_id,subject,message,created) VALUES(?,?,?,?)',(u['id'],subject,message,now()))
        c.commit()
    rows=c.execute('SELECT id,subject,message,status,created FROM support_tickets WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall();c.close()
    return jsonify(tickets=[dict(r) for r in rows])

@commercial.get('/api/admin/support')
def admin_support():
    admin();c=database();rows=c.execute('SELECT * FROM support_tickets ORDER BY id DESC LIMIT 200').fetchall();c.close()
    return jsonify(tickets=[dict(r) for r in rows])

@commercial.route('/api/lists',methods=['GET','POST'])
def lists():
    u=account();c=database()
    if request.method=='POST':
        name=required_text(payload().get('name'),80)
        c.execute('INSERT INTO user_book_lists(user_id,name,created) VALUES(?,?,?)',(u['id'],name,now()));c.commit()
    rows=c.execute('SELECT id,name,created FROM user_book_lists WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall()
    result=[]
    for row in rows:
        books=c.execute('SELECT b.id,b.title,b.author FROM user_book_list_items i JOIN books b ON b.id=i.book_id WHERE i.list_id=?',(row['id'],)).fetchall()
        result.append({**dict(row),'books':[dict(b) for b in books]})
    c.close();return jsonify(lists=result)

@commercial.post('/api/lists/<int:list_id>/books')
def add_list_book(list_id):
    u=account();data=payload();book_id=data.get('book_id')
    if type(book_id) is not int or book_id<1:abort(400)
    c=database()
    if not c.execute('SELECT 1 FROM user_book_lists WHERE id=? AND user_id=?',(list_id,u['id'])).fetchone():c.close();abort(404)
    if not c.execute('SELECT 1 FROM books WHERE id=?',(book_id,)).fetchone():c.close();abort(404)
    c.execute('INSERT OR IGNORE INTO user_book_list_items(list_id,book_id) VALUES(?,?)',(list_id,book_id));c.commit();c.close()
    return jsonify(ok=True)

@commercial.delete('/api/lists/<int:list_id>/books/<int:book_id>')
def remove_list_book(list_id,book_id):
    u=account();c=database()
    if not c.execute('SELECT 1 FROM user_book_lists WHERE id=? AND user_id=?',(list_id,u['id'])).fetchone():c.close();abort(404)
    c.execute('DELETE FROM user_book_list_items WHERE list_id=? AND book_id=?',(list_id,book_id));c.commit();c.close()
    return jsonify(ok=True)

@commercial.post('/api/admin/stock/<int:book_id>')
def adjust_stock(book_id):
    u=admin();data=payload();delta=data.get('delta');reason=required_text(data.get('reason'),200)
    if type(delta) is not int or not -10000<=delta<=10000 or delta==0:abort(400)
    c=database()
    try:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT stock FROM books WHERE id=?',(book_id,)).fetchone()
        if row is None:abort(404)
        if row['stock']+delta<0:abort(409,'Insufficient stock')
        c.execute('UPDATE books SET stock=stock+? WHERE id=?',(delta,book_id))
        c.execute('INSERT INTO book_stock_movements(book_id,delta,reason,actor_id,created) VALUES(?,?,?,?,?)',(book_id,delta,reason,u['id'],now()))
        c.commit()
        return jsonify(ok=True,stock=row['stock']+delta)
    finally:c.close()

@commercial.get('/api/admin/stock-history/<int:book_id>')
def stock_history(book_id):
    admin();c=database();rows=c.execute('SELECT * FROM book_stock_movements WHERE book_id=? ORDER BY id DESC',(book_id,)).fetchall();c.close()
    return jsonify(history=[dict(r) for r in rows])

@commercial.get('/api/admin/operations-summary')
def operations_summary():
    admin();c=database()
    counts={}
    for table in ('books','users','orders','loans','support_tickets','stock_movements'):
        actual='book_stock_movements' if table=='stock_movements' else table
        counts[table]=c.execute('SELECT COUNT(*) FROM '+actual).fetchone()[0]
    counts['low_stock']=c.execute('SELECT COUNT(*) FROM books WHERE stock<5').fetchone()[0]
    counts['open_support']=c.execute("SELECT COUNT(*) FROM support_tickets WHERE status='open'").fetchone()[0]
    c.close();return jsonify(counts)

@commercial.get('/api/security/csrf')
def csrf_token():
    """Same-origin clients fetch token then send it in X-CSRF-Token on writes."""
    account()
    import secrets
    return jsonify(csrf_token=session.setdefault('_csrf',secrets.token_urlsafe(32)))
