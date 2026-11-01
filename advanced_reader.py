"""Rights-aware accessible reader for locally licensed text; no unauthorized content fallback."""
from flask import Blueprint, abort, request, session, jsonify, redirect, url_for
from html import escape
from datetime import datetime, timezone

reader_plus = Blueprint('reader_plus', __name__)

def may_read(policy, signed_in, purchased=False, borrowed=False, is_admin=False):
    return policy == 'sample' or (policy == 'licensed' and (is_admin or (signed_in and (purchased or borrowed))))

def get_conn():
    from app import db
    return db()

def has_entitlement(conn, uid, book_id):
    if not uid:
        return False
    # A paid order is required; demo or pending orders do not grant access.
    paid = conn.execute("SELECT 1 FROM orders o JOIN order_items oi ON oi.order_id=o.id WHERE o.user_id=? AND oi.book_id=? AND lower(o.status) IN ('paid','completed','fulfilled') LIMIT 1", (uid,book_id)).fetchone() if table_exists(conn,'order_items') else None
    loan = conn.execute("SELECT 1 FROM loans WHERE user_id=? AND book_id=? AND lower(status) IN ('borrowed','active') AND (due IS NULL OR due >= date('now')) LIMIT 1",(uid,book_id)).fetchone()
    return bool(paid or loan)

def table_exists(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone() is not None

@reader_plus.get('/reader-plus/<int:book_id>')
def read(book_id):
    from app import page, current_user
    conn=get_conn()
    book=conn.execute('SELECT * FROM books WHERE id=?',(book_id,)).fetchone()
    if book is None:
        conn.close();abort(404)
    user=current_user()
    docs=conn.execute('SELECT * FROM licensed_documents WHERE book_id=? ORDER BY id',(book_id,)).fetchall()
    allowed=[]
    for d in docs:
        if may_read(d['access_policy'], bool(user), has_entitlement(conn,user['id'],book_id) if user else False, is_admin=bool(user and user['role']=='admin')):
            allowed.append(d)
    selected=request.args.get('document',type=int)
    document=next((d for d in allowed if d['id']==selected),None) if selected else (allowed[0] if allowed else None)
    chunks=conn.execute('SELECT chunk_number,content FROM licensed_chunks WHERE document_id=? ORDER BY chunk_number',(document['id'],)).fetchall() if document else []
    position=conn.execute('SELECT page,percent FROM progress WHERE user_id=? AND book_id=?',(user['id'],book_id)).fetchone() if user else None
    conn.close()
    return page('Accessible reader', '''<section class="card"><div class="row between"><div><span class="pill">Rights-aware reading</span><h1>{{book['title']}}</h1><p class="muted">{{book['author']}}</p></div><a class="btn ghost" href="/book/{{book['id']}}">Book details</a></div><div class="row"><label>Document <select id="document" onchange="location.href='/reader-plus/{{book['id']}}?document='+this.value">{% for d in docs %}<option value="{{d['id']}}" {% if selected and selected['id']==d['id'] %}selected{% endif %}>{{d['title']}}</option>{% endfor %}</select></label><label>Layout <select id="layout"><option value="spread">Two-page</option><option value="scroll">Continuous scroll</option></select></label><label>Text size <input type="range" id="size" min="16" max="32" value="20"></label><label>Line spacing <input type="range" id="spacing" min="1.3" max="2.4" step=".1" value="1.7"></label><button type="button" class="btn ghost" id="speak">Read aloud</button><button type="button" class="btn ghost" id="stop">Stop audio</button></div></section>{% if chunks %}<section id="accessible-reader" aria-label="Licensed book text" class="card" style="font-family:Georgia,serif;font-size:20px;line-height:1.7;max-width:1100px;column-count:2;column-gap:3rem"><h2 style="column-span:all">{{selected['title']}}</h2>{% for chunk in chunks %}<p id="chunk-{{chunk['chunk_number']}}">{{chunk['content']}}</p>{% endfor %}</section>{% else %}<section class="card"><h2>No accessible text for this title</h2><p>This book has no public sample or you do not have a verified entitlement to its licensed text. Contact the library or publisher for access. No copyrighted content is generated as a substitute.</p><a class="btn" href="/marketplace">Marketplace</a></section>{% endif %}{% if position %}<p class="muted">Saved position: page {{position['page']}} · {{position['percent']}}%</p>{% endif %}<script>(function(){const r=document.getElementById('accessible-reader');if(!r)return;const layout=document.getElementById('layout'),size=document.getElementById('size'),spacing=document.getElementById('spacing');layout.addEventListener('change',()=>r.style.columnCount=layout.value==='spread'?2:1);size.addEventListener('input',()=>r.style.fontSize=size.value+'px');spacing.addEventListener('input',()=>r.style.lineHeight=spacing.value);document.getElementById('speak').addEventListener('click',()=>{if(!('speechSynthesis' in window))return;window.speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance(r.innerText);window.speechSynthesis.speak(utterance)});document.getElementById('stop').addEventListener('click',()=>window.speechSynthesis?.cancel())})();</script>''',book=book,docs=allowed,selected=document,chunks=chunks,position=position)
