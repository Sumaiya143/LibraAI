"""Local, genuinely executable study tools. No AI provider or copyrighted content required."""
from datetime import date, timedelta
from flask import Blueprint, request, redirect, abort, flash
from markupsafe import escape
from extended import conn, user

bp = Blueprint('learning', __name__, url_prefix='/learning')

def initialize():
    with conn() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS learning_goals(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL, title TEXT NOT NULL, target_pages INTEGER NOT NULL CHECK(target_pages>0), current_pages INTEGER NOT NULL DEFAULT 0, deadline TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS learning_reviews(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,flashcard_id INTEGER NOT NULL, grade INTEGER NOT NULL, reviewed_at TEXT NOT NULL);
        ''')

from scheduling import schedule

def require_user():
    u=user()
    if u is None: abort(401)
    return u

@bp.route('/')
def index():
    from app import page
    u=require_user()
    with conn() as c:
        goals=c.execute('SELECT * FROM learning_goals WHERE user_id=? ORDER BY deadline',(u['id'],)).fetchall()
        cards=c.execute('SELECT f.*,b.title FROM flashcards f JOIN books b ON b.id=f.book_id WHERE f.user_id=? AND f.due<=? ORDER BY f.due LIMIT 30',(u['id'],date.today().isoformat())).fetchall()
    goals_html=''.join(f'<div class="card"><b>{escape(g["title"])}</b><p>{g["current_pages"]}/{g["target_pages"]} pages · deadline {escape(g["deadline"])}</p><form method="post" action="/learning/goals/{g["id"]}/progress"><input class="input" name="pages" type="number" min="1" max="500" value="10" required><button class="btn">Log pages</button></form></div>' for g in goals)
    cards_html=''.join(f'<div class="card"><span class="pill">{escape(x["title"])}</span><h3>{escape(x["front"])}</h3><details><summary>Reveal answer</summary><p>{escape(x["back"])}</p></details><form method="post" action="/learning/cards/{x["id"]}/review"><label>Recall quality (0–5)</label><select name="grade">'+''.join(f'<option value="{i}">{i}</option>' for i in range(6))+' </select><button class="btn">Save review</button></form></div>' for x in cards)
    body=f'''<h1>Learning studio</h1><p class="muted">Real locally saved goals, reading progress and spaced-repetition review scheduling.</p><div class="card"><h2>New reading goal</h2><form method="post" action="/learning/goals"><input class="input" name="title" placeholder="Goal title" maxlength="120" required><input class="input" name="target_pages" type="number" min="1" max="100000" placeholder="Target pages" required><input class="input" name="deadline" type="date" min="{date.today().isoformat()}" required><button class="btn">Create goal</button></form></div><h2>My goals</h2><div class="grid">{goals_html or '<p>No goals yet.</p>'}</div><h2>Flashcards due today ({len(cards)})</h2><div class="grid">{cards_html or '<p>All caught up! Add cards from Study Tools.</p>'}</div>'''
    return page('Learning studio',body)

@bp.post('/goals')
def create_goal():
    u=require_user()
    title=request.form.get('title','').strip()[:120]
    try: target=int(request.form.get('target_pages','0')); deadline=date.fromisoformat(request.form.get('deadline',''))
    except (ValueError,TypeError): abort(400)
    if not title or not 1<=target<=100000 or deadline<date.today(): abort(400)
    with conn() as c: c.execute('INSERT INTO learning_goals(user_id,title,target_pages,deadline) VALUES(?,?,?,?)',(u['id'],title,target,deadline.isoformat()))
    flash('Goal created'); return redirect('/learning/')

@bp.post('/goals/<int:goal_id>/progress')
def log_pages(goal_id):
    u=require_user()
    try: pages=int(request.form.get('pages','0'))
    except ValueError: abort(400)
    if not 1<=pages<=500: abort(400)
    with conn() as c:
        cur=c.execute('UPDATE learning_goals SET current_pages=MIN(target_pages,current_pages+?) WHERE id=? AND user_id=?',(pages,goal_id,u['id']))
        if not cur.rowcount: abort(404)
    return redirect('/learning/')

@bp.post('/cards/<int:card_id>/review')
def review_card(card_id):
    u=require_user()
    try: grade=int(request.form.get('grade','-1'))
    except ValueError: abort(400)
    if grade not in range(6): abort(400)
    with conn() as c:
        card=c.execute('SELECT * FROM flashcards WHERE id=? AND user_id=?',(card_id,u['id'])).fetchone()
        if not card: abort(404)
        interval,due=schedule(card['interval_days'],grade)
        c.execute('UPDATE flashcards SET interval_days=?,due=? WHERE id=? AND user_id=?',(interval,due.isoformat(),card_id,u['id']))
        c.execute('INSERT INTO learning_reviews(user_id,flashcard_id,grade,reviewed_at) VALUES(?,?,?,?)',(u['id'],card_id,grade,date.today().isoformat()))
    return redirect('/learning/')
