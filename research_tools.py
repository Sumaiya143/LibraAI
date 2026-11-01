"""Real local research utilities; never claims to have accessed licensed full text."""
from flask import Blueprint, request, jsonify, session, abort, Response, render_template_string
import sqlite3, os, json, re, html
from datetime import datetime
bp = Blueprint('research_tools', __name__, url_prefix='/research')
DB=os.environ.get('LIBRAAI_DB_PATH',os.path.join(os.path.dirname(__file__),'libraai.db'))
def conn():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def require_user():
 if not session.get('uid'): abort(401,description='Sign in required')
 return session['uid']

def book(book_id):
 c=conn(); b=c.execute('SELECT * FROM books WHERE id=?',(book_id,)).fetchone(); c.close()
 if b is None: abort(404)
 return dict(b)

def cite(b,style):
 author=b['author']; year=b['year']; title=b['title']
 if style=='mla': return f'{author}. {title}. {year}.'
 if style=='chicago': return f'{author}. {title}. {year}.'
 return f'{author}. ({year}). {title}.'

@bp.get('/')
def index():
 require_user(); c=conn(); books=[dict(b) for b in c.execute('SELECT id,title,author FROM books ORDER BY title')]; c.close()
 return render_template_string('''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>LibraAI Research</title><style>body{font:16px system-ui;background:#f5f7ff;color:#1d2850;max-width:1000px;margin:30px auto;padding:16px}article{background:white;padding:22px;border-radius:16px;margin:12px 0}button,select,input{padding:10px;border:1px solid #cbd2ed;border-radius:8px;margin:5px}button{background:#5657d9;color:white;cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style></head><body><a href="/">← Dashboard</a><h1>Research workspace</h1><p>Book comparisons, catalog search, citations, reading-time estimates, and a metadata knowledge graph. No copyrighted book content is reproduced.</p><article><h2>Compare books</h2><select id="a">{% for b in books %}<option value="{{b.id}}">{{b.title}}</option>{% endfor %}</select><select id="b">{% for b in books %}<option value="{{b.id}}">{{b.title}}</option>{% endfor %}</select><button onclick="load('/research/api/compare?ids='+a.value+','+b.value)">Compare</button></article><article><h2>Citation generator</h2><select id="c">{% for b in books %}<option value="{{b.id}}">{{b.title}}</option>{% endfor %}</select><select id="style"><option>apa</option><option>mla</option><option>chicago</option></select><button onclick="load('/research/api/citation/'+c.value+'?style='+style.value)">Generate</button></article><article><h2>Reading-time estimator</h2><input id="words" type="number" min="1" value="40000" aria-label="Word count"><input id="wpm" type="number" min="50" max="1000" value="220" aria-label="Words per minute"><button onclick="load('/research/api/reading-time?words='+words.value+'&wpm='+wpm.value)">Estimate</button></article><article><h2>Catalog knowledge graph</h2><button onclick="load('/research/api/graph')">Explore connections</button></article><article><h2>Results</h2><pre id="result" aria-live="polite">Choose a tool above.</pre></article><script>async function load(url){const r=await fetch(url);document.getElementById('result').textContent=JSON.stringify(await r.json(),null,2)}</script></body></html>''',books=books)

@bp.get('/api/compare')
def compare():
 require_user(); ids=request.args.get('ids','').split(',')
 if len(ids)!=2 or not all(re.fullmatch(r'\d+',x or '') for x in ids): abort(400)
 a,b=(book(int(i)) for i in ids)
 keys=['title','author','genre','rating','reads','sales','year','format','price','language','isbn','branch','shelf']
 return jsonify({'books':[{k:item[k] for k in keys} for item in [a,b]],'shared_genre':a['genre']==b['genre'],'note':'Metadata comparison only; no full-text analysis'})

@bp.get('/api/citation/<int:book_id>')
def citation(book_id):
 require_user(); style=request.args.get('style','apa').lower()
 if style not in ('apa','mla','chicago'): abort(400)
 b=book(book_id)
 return jsonify({'citation':cite(b,style),'style':style,'notice':'Basic citation generated from catalog metadata; verify publisher/edition before academic submission'})

@bp.get('/api/reading-time')
def reading_time():
 require_user()
 try: words=int(request.args.get('words','0')); wpm=int(request.args.get('wpm','220'))
 except ValueError: abort(400)
 if not 1<=words<=10000000 or not 50<=wpm<=1000: abort(400)
 return jsonify({'minutes':round(words/wpm,1),'hours':round(words/wpm/60,2),'words':words,'words_per_minute':wpm})

@bp.get('/api/graph')
def graph():
 require_user(); c=conn(); books=[dict(x) for x in c.execute('SELECT id,title,author,genre FROM books')]; c.close()
 nodes=[{'id':f'book:{b["id"]}','label':b['title'],'type':'book'} for b in books]
 edges=[]; seen=set()
 for b in books:
  for kind,val in [('author',b['author']),('genre',b['genre'])]:
   key=f'{kind}:{val}'
   if key not in seen: nodes.append({'id':key,'label':val,'type':kind}); seen.add(key)
   edges.append({'source':f'book:{b["id"]}','target':key,'relation':kind})
 return jsonify({'nodes':nodes,'edges':edges,'scope':'Catalog metadata only'})

@bp.get('/api/search')
def cross_book_search():
 require_user(); q=request.args.get('q','').strip()[:100]
 if not q:return jsonify({'results':[]})
 c=conn(); rows=[dict(x) for x in c.execute('SELECT id,title,author,description,genre FROM books WHERE title LIKE ? OR description LIKE ? OR author LIKE ? LIMIT 50',tuple('%'+q+'%' for _ in range(3)))]; c.close()
 return jsonify({'results':rows,'scope':'Catalog metadata, not copyrighted full text'})

@bp.get('/api/export-notes')
def export_notes():
 uid=require_user(); c=conn(); rows=[dict(x) for x in c.execute('SELECT book_id,kind,content,color,page,created FROM annotations WHERE user_id=? ORDER BY created',(uid,))]; c.close()
 return Response(json.dumps(rows,ensure_ascii=False,indent=2),mimetype='application/json',headers={'Content-Disposition':'attachment; filename="libraai-my-notes.json"'})
