"""Shared API foundations for LibraAI's reading, creator and personalization ecosystem.

This module intentionally uses the application's existing SQLite database and session
identity. It does not pretend to provide a hosted AI/payment service: recommendations
are catalog-grounded, while payment provider completion remains a separate integration.
"""
from flask import Blueprint, request, jsonify
from datetime import date, datetime
import sqlite3

ecosystem_bp = Blueprint('ecosystem_api', __name__)

def setup_ecosystem(db):
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS reading_goals(
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          target_minutes INTEGER NOT NULL DEFAULT 300, target_books INTEGER NOT NULL DEFAULT 1,
          period_start TEXT NOT NULL DEFAULT (date('now')), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(user_id, period_start));
        CREATE TABLE IF NOT EXISTS reading_sessions(
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          book_id INTEGER REFERENCES books(id) ON DELETE SET NULL, minutes INTEGER NOT NULL,
          pages INTEGER NOT NULL DEFAULT 0, session_date TEXT NOT NULL DEFAULT (date('now')),
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS knowledge_notes(
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          book_id INTEGER REFERENCES books(id) ON DELETE SET NULL, title TEXT NOT NULL,
          content TEXT NOT NULL, tags TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS creator_submissions(
          id INTEGER PRIMARY KEY, creator_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          title TEXT NOT NULL, content_type TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          reviewed_at TEXT);
        CREATE TABLE IF NOT EXISTS user_preferences(
          user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
          favorite_genres TEXT NOT NULL DEFAULT '', preferred_language TEXT NOT NULL DEFAULT 'Any',
          font_scale INTEGER NOT NULL DEFAULT 100, reading_theme TEXT NOT NULL DEFAULT 'light',
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS user_notifications(
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '',
          read_at TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        ''')

def _user(current_user):
    u=current_user()
    if not u: return None
    try: return dict(u)
    except Exception: return u

def install_ecosystem(app, db, current_user):
    @ecosystem_bp.get('/api/ecosystem/health')
    def ecosystem_health():
        with db() as c:
            counts={k:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for k,t in {
              'catalog':'books','creator_submissions':'creator_submissions','notes':'knowledge_notes',
              'reading_sessions':'reading_sessions','chapters':'manga_chapters','products':'catalog_products'}.items()}
        return jsonify({'ok':True,'service':'libraai-ecosystem','storage':'shared-app-database','counts':counts})

    @ecosystem_bp.get('/api/ecosystem/recommendations')
    def recommendations():
        q=(request.args.get('q') or '').strip().lower()[:160]
        genres=[x.strip().lower() for x in (request.args.get('genres') or '').split(',') if x.strip()][:8]
        language=(request.args.get('language') or '').strip().lower()
        limit=min(24,max(1,request.args.get('limit',12,type=int)))
        with db() as c:
            rows=c.execute('''SELECT b.*,COALESCE(cp.product_type,'physical_book') product_type,
              COALESCE(cp.sale_enabled,1) sale_enabled,COALESCE(cp.digital_available,0) digital_available,
              COALESCE(cp.inventory_quantity,b.stock,0) inventory_quantity
              FROM books b LEFT JOIN catalog_products cp ON cp.book_id=b.id''').fetchall()
        items=[]
        for r in rows:
            d=dict(r); genre=str(d.get('genre') or '').lower(); title=str(d.get('title') or '').lower(); desc=str(d.get('description') or '').lower(); author=str(d.get('author') or '').lower(); lang=str(d.get('language') or '').lower()
            score=0; reasons=[]
            if q:
                terms=[x for x in q.split() if len(x)>1]
                hits=sum(1 for t in terms if t in genre or t in title or t in desc or t in author)
                score+=hits*3
                if hits: reasons.append('Matches your description')
            for g in genres:
                if g in genre or g in title or g in desc: score+=5; reasons.append('Matches a preferred genre'); break
            if language and language not in ('any','any language'):
                if language in lang: score+=2
                else: score-=2
            score+=min(float(d.get('rating') or 0),5)*0.2
            if score>0 or (not q and not genres and not language):
                stock=int(d.get('inventory_quantity') or 0); digital=bool(d.get('digital_available')); enabled=bool(d.get('sale_enabled'))
                d['availability_status']='Unavailable' if not enabled else ('Available Online' if digital else ('In Stock' if stock>0 else 'Out of Stock'))
                d['recommendation_score']=round(score,2); d['recommendation_reasons']=list(dict.fromkeys(reasons)) or ['Popular catalog match']
                items.append(d)
        items.sort(key=lambda x:(x['recommendation_score'],float(x.get('rating') or 0)),reverse=True)
        return jsonify({'items':items[:limit],'strategy':'catalog-grounded preference matching','ai_generated_claims':False})

    @ecosystem_bp.route('/api/ecosystem/preferences',methods=['GET','PUT'])
    def preferences():
        u=_user(current_user)
        if not u: return jsonify({'error':'Sign in required'}),401
        uid=u['id']
        with db() as c:
            if request.method=='PUT':
                data=request.get_json(silent=True) or {}; genres=data.get('favorite_genres',''); lang=data.get('preferred_language','Any'); scale=data.get('font_scale',100); theme=data.get('reading_theme','light')
                if not isinstance(genres,str) or len(genres)>500 or not isinstance(lang,str) or len(lang)>40 or not isinstance(theme,str) or theme not in ('light','sepia','dark') or not isinstance(scale,int) or not 80<=scale<=180: return jsonify({'error':'Invalid preference values'}),400
                c.execute('''INSERT INTO user_preferences(user_id,favorite_genres,preferred_language,font_scale,reading_theme,updated_at) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(user_id) DO UPDATE SET favorite_genres=excluded.favorite_genres,preferred_language=excluded.preferred_language,font_scale=excluded.font_scale,reading_theme=excluded.reading_theme,updated_at=CURRENT_TIMESTAMP''',(uid,genres,lang,scale,theme))
            row=c.execute('SELECT favorite_genres,preferred_language,font_scale,reading_theme,updated_at FROM user_preferences WHERE user_id=?',(uid,)).fetchone()
        return jsonify(dict(row) if row else {'favorite_genres':'','preferred_language':'Any','font_scale':100,'reading_theme':'light'})

    @ecosystem_bp.route('/api/ecosystem/reading-sessions',methods=['GET','POST'])
    def reading_sessions():
        u=_user(current_user)
        if not u:return jsonify({'error':'Sign in required'}),401
        with db() as c:
            if request.method=='POST':
                d=request.get_json(silent=True) or {}; minutes=d.get('minutes'); pages=d.get('pages',0); book_id=d.get('book_id')
                if not isinstance(minutes,int) or not 1<=minutes<=1440 or not isinstance(pages,int) or not 0<=pages<=10000:return jsonify({'error':'minutes (1–1440) and pages (0–10000) are required'}),400
                if book_id is not None and not c.execute('SELECT 1 FROM books WHERE id=?',(book_id,)).fetchone():return jsonify({'error':'Unknown book'}),404
                c.execute('INSERT INTO reading_sessions(user_id,book_id,minutes,pages) VALUES(?,?,?,?)',(u['id'],book_id,minutes,pages)); c.commit()
            rows=c.execute('SELECT rs.id,rs.book_id,b.title,rs.minutes,rs.pages,rs.session_date,rs.created_at FROM reading_sessions rs LEFT JOIN books b ON b.id=rs.book_id WHERE rs.user_id=? ORDER BY rs.created_at DESC LIMIT 100',(u['id'],)).fetchall()
            totals=c.execute('SELECT COALESCE(SUM(minutes),0) minutes,COALESCE(SUM(pages),0) pages,COUNT(DISTINCT book_id) books FROM reading_sessions WHERE user_id=?',(u['id'],)).fetchone()
        return jsonify({'items':[dict(r) for r in rows],'totals':dict(totals)})

    @ecosystem_bp.route('/api/ecosystem/knowledge-notes',methods=['GET','POST'])
    def knowledge_notes():
        u=_user(current_user)
        if not u:return jsonify({'error':'Sign in required'}),401
        with db() as c:
            if request.method=='POST':
                d=request.get_json(silent=True) or {}; title=d.get('title','').strip() if isinstance(d.get('title',''),str) else ''; content=d.get('content','').strip() if isinstance(d.get('content',''),str) else ''; tags=d.get('tags','') if isinstance(d.get('tags',''),str) else ''
                if not title or len(title)>180 or not content or len(content)>20000 or len(tags)>500:return jsonify({'error':'Valid title, content and tags are required'}),400
                bid=d.get('book_id')
                if bid is not None and not c.execute('SELECT 1 FROM books WHERE id=?',(bid,)).fetchone():return jsonify({'error':'Unknown book'}),404
                cur=c.execute('INSERT INTO knowledge_notes(user_id,book_id,title,content,tags) VALUES(?,?,?,?,?)',(u['id'],bid,title,content,tags)); c.commit()
                return jsonify({'ok':True,'id':cur.lastrowid}),201
            rows=c.execute('SELECT id,book_id,title,content,tags,created_at,updated_at FROM knowledge_notes WHERE user_id=? ORDER BY updated_at DESC LIMIT 200',(u['id'],)).fetchall()
        return jsonify({'items':[dict(r) for r in rows]})

    @ecosystem_bp.post('/api/ecosystem/creator/submissions')
    def creator_submission():
        u=_user(current_user)
        if not u:return jsonify({'error':'Sign in required'}),401
        d=request.get_json(silent=True) or {}; title=d.get('title','').strip() if isinstance(d.get('title',''),str) else ''; kind=d.get('content_type','')
        desc=d.get('description','') if isinstance(d.get('description',''),str) else ''
        if not title or len(title)>180 or kind not in ('ebook','audiobook','manga','physical_book','study_material') or len(desc)>3000:return jsonify({'error':'Valid title, content_type and description required'}),400
        with db() as c:
            cur=c.execute('INSERT INTO creator_submissions(creator_id,title,content_type,description) VALUES(?,?,?,?)',(u['id'],title,kind,desc)); c.commit()
        return jsonify({'ok':True,'submission_id':cur.lastrowid,'status':'pending_review'}),201

    @ecosystem_bp.get('/api/ecosystem/analytics/me')
    def analytics_me():
        u=_user(current_user)
        if not u:return jsonify({'error':'Sign in required'}),401
        with db() as c:
            totals=c.execute('SELECT COALESCE(SUM(minutes),0) minutes,COALESCE(SUM(pages),0) pages,COUNT(DISTINCT book_id) books FROM reading_sessions WHERE user_id=?',(u['id'],)).fetchone()
            notes=c.execute('SELECT COUNT(*) FROM knowledge_notes WHERE user_id=?',(u['id'],)).fetchone()[0]
            subs=c.execute("SELECT COUNT(*) FROM subscription_entitlements WHERE user_id=? AND status='active' AND (expires_at IS NULL OR expires_at>CURRENT_TIMESTAMP)",(u['id'],)).fetchone()[0]
            sessions=c.execute("SELECT COUNT(*) FROM reading_sessions WHERE user_id=? AND session_date>=date('now','-6 days')",(u['id'],)).fetchone()[0]
        return jsonify({'reading':dict(totals),'knowledge_notes':notes,'active_memberships':subs,'sessions_last_7_days':sessions})

    @ecosystem_bp.route('/api/ecosystem/reading-goals', methods=['GET','PUT'])
    def reading_goals():
        u=_user(current_user)
        if not u: return jsonify({'error':'Sign in required'}),401
        with db() as c:
            if request.method=='PUT':
                d=request.get_json(silent=True) or {}; minutes=d.get('target_minutes',300); books=d.get('target_books',1)
                if type(minutes) is not int or not 15<=minutes<=10000 or type(books) is not int or not 1<=books<=100:
                    return jsonify({'error':'target_minutes must be 15–10000 and target_books 1–100'}),400
                c.execute("""INSERT INTO reading_goals(user_id,target_minutes,target_books,period_start) VALUES(?,?,?,date('now','start of month'))
                    ON CONFLICT(user_id,period_start) DO UPDATE SET target_minutes=excluded.target_minutes,target_books=excluded.target_books""",(u['id'],minutes,books))
            row=c.execute("SELECT target_minutes,target_books,period_start FROM reading_goals WHERE user_id=? AND period_start=date('now','start of month')",(u['id'],)).fetchone()
            totals=c.execute("SELECT COALESCE(SUM(minutes),0) minutes,COUNT(DISTINCT book_id) books FROM reading_sessions WHERE user_id=? AND session_date>=date('now','start of month')",(u['id'],)).fetchone()
        goal=dict(row) if row else {'target_minutes':300,'target_books':1,'period_start':date.today().replace(day=1).isoformat()}
        goal['progress_minutes']=int(totals['minutes']); goal['progress_books']=int(totals['books'])
        goal['minutes_percent']=min(100,round(goal['progress_minutes']/max(1,goal['target_minutes'])*100))
        goal['books_percent']=min(100,round(goal['progress_books']/max(1,goal['target_books'])*100))
        return jsonify(goal),200,{'Cache-Control':'private, no-store'}

    @ecosystem_bp.get('/api/ecosystem/notifications')
    def ecosystem_notifications():
        u=_user(current_user)
        if not u:return jsonify({'error':'Sign in required'}),401
        with db() as c:
            rows=c.execute('SELECT id,kind,title,body,read_at,created_at FROM user_notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 100',(u['id'],)).fetchall()
        return jsonify({'items':[dict(r) for r in rows]}),200,{'Cache-Control':'private, no-store'}

    @ecosystem_bp.post('/api/ecosystem/notifications/<int:notification_id>/read')
    def mark_ecosystem_notification_read(notification_id):
        u=_user(current_user)
        if not u:return jsonify({'error':'Sign in required'}),401
        with db() as c:
            cur=c.execute("UPDATE user_notifications SET read_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",(notification_id,u['id']))
            if not cur.rowcount:return jsonify({'error':'Notification not found'}),404
        return jsonify({'ok':True,'id':notification_id,'read':True}),200

    @ecosystem_bp.get('/api/admin/ecosystem/creator-submissions')
    def admin_creator_submissions():
        u=_user(current_user)
        if not u:return jsonify({'error':'Sign in required'}),401
        if u.get('role')!='admin':return jsonify({'error':'Admin role required'}),403
        with db() as c:
            rows=c.execute("SELECT s.id,s.creator_id,u.name AS creator_name,s.title,s.content_type,s.description,s.status,s.created_at,s.reviewed_at FROM creator_submissions s JOIN users u ON u.id=s.creator_id ORDER BY CASE s.status WHEN 'pending' THEN 0 ELSE 1 END,s.created_at DESC LIMIT 300").fetchall()
        return jsonify({'items':[dict(r) for r in rows]}),200,{'Cache-Control':'no-store'}

    @ecosystem_bp.post('/api/admin/ecosystem/creator-submissions/<int:submission_id>/review')
    def review_creator_submission(submission_id):
        u=_user(current_user)
        if not u:return jsonify({'error':'Sign in required'}),401
        if u.get('role')!='admin':return jsonify({'error':'Admin role required'}),403
        d=request.get_json(silent=True) or {}; status=d.get('status')
        if status not in ('approved','rejected','pending'):return jsonify({'error':'status must be approved, rejected or pending'}),400
        with db() as c:
            cur=c.execute('UPDATE creator_submissions SET status=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?',(status,submission_id))
            if not cur.rowcount:return jsonify({'error':'Submission not found'}),404
            row=c.execute('SELECT id,title,content_type,status,reviewed_at FROM creator_submissions WHERE id=?',(submission_id,)).fetchone()
        return jsonify({'ok':True,'submission':dict(row)}),200

    app.register_blueprint(ecosystem_bp)

# Additional operational APIs: goals, notifications, and moderated creator review.
# These share the same persistent database and session identity as the core app.
