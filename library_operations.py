"""Operational APIs for member administration, circulation, reservations, branches and reader analytics."""
from datetime import datetime, timedelta, timezone
from flask import request, jsonify
import sqlite3


def install(app, db, current_user):
    def actor():
        u = current_user()
        if not u:
            return None, (jsonify({'error':'Authentication required'}), 401)
        return u, None

    def staff(u):
        return str(u['role'] or '').lower() in ('admin','librarian')

    def admin(u):
        return str(u['role'] or '').lower() == 'admin'

    def setup(c):
        c.executescript('''
        CREATE TABLE IF NOT EXISTS member_controls(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,status TEXT NOT NULL DEFAULT 'active',updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS library_branches(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,code TEXT NOT NULL UNIQUE,address TEXT NOT NULL DEFAULT '',city TEXT NOT NULL DEFAULT '',phone TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'active',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS branch_inventory(branch_id INTEGER NOT NULL REFERENCES library_branches(id),book_id INTEGER NOT NULL REFERENCES books(id),copies INTEGER NOT NULL DEFAULT 0 CHECK(copies>=0),PRIMARY KEY(branch_id,book_id));
        CREATE TABLE IF NOT EXISTS circulation_events(id INTEGER PRIMARY KEY,loan_id INTEGER NOT NULL REFERENCES loans(id),actor_id INTEGER NOT NULL REFERENCES users(id),event TEXT NOT NULL,branch_id INTEGER,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS book_reservations(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),book_id INTEGER NOT NULL REFERENCES books(id),branch_id INTEGER REFERENCES library_branches(id),status TEXT NOT NULL DEFAULT 'queued',queue_position INTEGER,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(user_id,book_id,status));
        CREATE TABLE IF NOT EXISTS library_reading_sessions(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),book_id INTEGER NOT NULL REFERENCES books(id),started_at TEXT NOT NULL,ended_at TEXT,seconds INTEGER NOT NULL DEFAULT 0 CHECK(seconds>=0),genre TEXT NOT NULL DEFAULT 'Uncategorized',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS idx_library_reading_sessions_user_date ON library_reading_sessions(user_id,started_at);
        CREATE INDEX IF NOT EXISTS idx_reservations_status ON book_reservations(status,created_at);
        CREATE INDEX IF NOT EXISTS idx_loans_status_due ON loans(status,due);
        ''')
        # Migrate pre-existing branches without replacing their data.
        for row in c.execute('SELECT DISTINCT branch FROM books WHERE COALESCE(branch,"")<>""').fetchall():
            name = str(row['branch']).strip()[:100]
            if name:
                code = ''.join(ch for ch in name.upper() if ch.isalnum())[:12] or 'BRANCH'
                candidate = code; suffix = 1
                while c.execute('SELECT 1 FROM library_branches WHERE code=?',(candidate,)).fetchone():
                    suffix += 1; candidate = (code[:8]+str(suffix))[:12]
                c.execute('INSERT OR IGNORE INTO library_branches(name,code,city) VALUES(?,?,?)',(name,candidate,''))
        c.execute('''INSERT OR IGNORE INTO branch_inventory(branch_id,book_id,copies)
          SELECT br.id,b.id,MAX(COALESCE(b.stock,0),0) FROM library_branches br JOIN books b ON b.branch=br.name''')
        c.commit()

    with app.app_context():
        with db() as c: setup(c)

    @app.get('/api/admin/members')
    def api_admin_members():
        u, err = actor()
        if err: return err
        if not staff(u): return jsonify({'error':'Library staff access required'}),403
        q=request.args.get('q','').strip()[:100]
        with db() as c:
            rows=c.execute('''SELECT u.id,u.name,u.username,u.email,u.role,u.plan,COALESCE(mc.status,'active') status
              FROM users u LEFT JOIN member_controls mc ON mc.user_id=u.id
              WHERE (?='' OR u.name LIKE ? OR u.email LIKE ? OR u.username LIKE ?) ORDER BY u.id DESC LIMIT 300''',(q,'%'+q+'%','%'+q+'%','%'+q+'%')).fetchall()
        return jsonify({'items':[dict(r) for r in rows]})

    @app.patch('/api/admin/members/<int:member_id>')
    def api_admin_member_update(member_id):
        u,err=actor()
        if err:return err
        if not admin(u):return jsonify({'error':'Administrator access required'}),403
        b=request.get_json(silent=True) or {}; status=b.get('status'); role=b.get('role')
        if status not in (None,'active','suspended') or role not in (None,'reader','merchant','librarian','admin'):
            return jsonify({'error':'Invalid member status or role'}),400
        if member_id==u['id'] and (status=='suspended' or role not in (None,'admin')):
            return jsonify({'error':'You cannot suspend or demote your own administrator account'}),400
        with db() as c:
            if not c.execute('SELECT id FROM users WHERE id=?',(member_id,)).fetchone():return jsonify({'error':'Member not found'}),404
            if status is not None:c.execute('INSERT INTO member_controls(user_id,status) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET status=excluded.status,updated_at=CURRENT_TIMESTAMP',(member_id,status))
            if role is not None:c.execute('UPDATE users SET role=? WHERE id=?',(role,member_id))
            c.execute('INSERT INTO audit(user_id,action,created) VALUES(?,?,?)',(u['id'],f'Updated member #{member_id}',datetime.now(timezone.utc).isoformat()))
            row=c.execute("SELECT u.id,u.name,u.email,u.role,COALESCE(mc.status,'active') status FROM users u LEFT JOIN member_controls mc ON mc.user_id=u.id WHERE u.id=?",(member_id,)).fetchone()
        return jsonify(dict(row))

    @app.get('/api/admin/circulation')
    def api_circulation_list():
        u,err=actor()
        if err:return err
        if not staff(u):return jsonify({'error':'Library staff access required'}),403
        with db() as c:
            rows=c.execute('SELECT l.id,l.user_id,u.name member_name,u.email,b.title book_title,l.status,l.due,l.branch,l.created FROM loans l JOIN users u ON u.id=l.user_id JOIN books b ON b.id=l.book_id ORDER BY l.id DESC LIMIT 500').fetchall()
        return jsonify({'items':[dict(r) for r in rows]})

    @app.post('/api/admin/circulation/issue')
    def api_circulation_issue():
        u,err=actor()
        if err:return err
        if not staff(u):return jsonify({'error':'Library staff access required'}),403
        b=request.get_json(silent=True) or {}; uid=b.get('user_id'); bid=b.get('book_id'); branch=(b.get('branch') or '').strip()[:100]; days=b.get('days',14)
        if not all(isinstance(x,int) and not isinstance(x,bool) and x>0 for x in (uid,bid)) or not isinstance(days,int) or not 1<=days<=90:return jsonify({'error':'Valid member, book and 1–90 day loan period required'}),400
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            member=c.execute("SELECT id FROM users WHERE id=?",(uid,)).fetchone(); book=c.execute('SELECT id,stock,branch FROM books WHERE id=?',(bid,)).fetchone()
            if not member or not book:return jsonify({'error':'Member or book not found'}),404
            active=c.execute("SELECT 1 FROM loans WHERE user_id=? AND book_id=? AND lower(status) IN ('issued','active','borrowed')",(uid,bid)).fetchone()
            if active:return jsonify({'error':'This member already has an active loan for this book'}),409
            branch=branch or book['branch'] or 'Central'
            branchrow=c.execute('SELECT id FROM library_branches WHERE name=? AND status=\'active\'',(branch,)).fetchone()
            if not branchrow:return jsonify({'error':'Select an active library branch'}),400
            inventory=c.execute('SELECT copies FROM branch_inventory WHERE branch_id=? AND book_id=?',(branchrow['id'],bid)).fetchone()
            if inventory is not None:
                if inventory['copies']<1:return jsonify({'error':'No available copy at this branch'}),409
                c.execute('UPDATE branch_inventory SET copies=copies-1 WHERE branch_id=? AND book_id=?',(branchrow['id'],bid))
            else:
                if int(book['stock'] or 0)<1:return jsonify({'error':'No available copy for this book'}),409
                c.execute('UPDATE books SET stock=COALESCE(stock,0)-1 WHERE id=?',(bid,))
            due=(datetime.now(timezone.utc)+timedelta(days=days)).date().isoformat()
            cur=c.execute("INSERT INTO loans(user_id,book_id,status,due,branch,created) VALUES(?,?,'issued',?,?,?)",(uid,bid,due,branch,datetime.now(timezone.utc).isoformat()))
            c.execute('INSERT INTO circulation_events(loan_id,actor_id,event,branch_id) VALUES(?,?,?,?)',(cur.lastrowid,u['id'],'issued',branchrow['id']))
        return jsonify({'ok':True,'loan_id':cur.lastrowid,'due':due}),201

    @app.post('/api/admin/circulation/<int:loan_id>/return')
    def api_circulation_return(loan_id):
        u,err=actor()
        if err:return err
        if not staff(u):return jsonify({'error':'Library staff access required'}),403
        with db() as c:
            c.execute('BEGIN IMMEDIATE'); loan=c.execute('SELECT * FROM loans WHERE id=?',(loan_id,)).fetchone()
            if not loan:return jsonify({'error':'Loan not found'}),404
            if str(loan['status']).lower() not in ('issued','active','borrowed'):return jsonify({'error':'Loan is not currently active'}),409
            c.execute("UPDATE loans SET status='returned' WHERE id=?",(loan_id,))
            br=c.execute('SELECT id FROM library_branches WHERE name=?',(loan['branch'],)).fetchone()
            if br:
                inv=c.execute('SELECT copies FROM branch_inventory WHERE branch_id=? AND book_id=?',(br['id'],loan['book_id'])).fetchone()
                if inv:c.execute('UPDATE branch_inventory SET copies=copies+1 WHERE branch_id=? AND book_id=?',(br['id'],loan['book_id']))
                else:c.execute('UPDATE books SET stock=COALESCE(stock,0)+1 WHERE id=?',(loan['book_id'],))
            else:c.execute('UPDATE books SET stock=COALESCE(stock,0)+1 WHERE id=?',(loan['book_id'],))
            c.execute('INSERT INTO circulation_events(loan_id,actor_id,event,branch_id) VALUES(?,?,?,?)',(loan_id,u['id'],'returned',br['id'] if br else None))
        return jsonify({'ok':True,'loan_id':loan_id,'status':'returned'})

    @app.get('/api/admin/reservations')
    def api_reservations_list():
        u,err=actor()
        if err:return err
        if not staff(u):return jsonify({'error':'Library staff access required'}),403
        with db() as c:
            rows=c.execute('SELECT r.id,r.user_id,u.name member_name,r.book_id,b.title book_title,r.branch_id,br.name branch,r.status,r.queue_position,r.created_at FROM book_reservations r JOIN users u ON u.id=r.user_id JOIN books b ON b.id=r.book_id LEFT JOIN library_branches br ON br.id=r.branch_id ORDER BY CASE r.status WHEN \'queued\' THEN 0 WHEN \'ready\' THEN 1 ELSE 2 END,r.created_at').fetchall()
        return jsonify({'items':[dict(r) for r in rows]})

    @app.post('/api/reservations')
    def api_reservation_create():
        u,err=actor()
        if err:return err
        b=request.get_json(silent=True) or {}; bid=b.get('book_id'); branch_id=b.get('branch_id')
        if not isinstance(bid,int) or isinstance(bid,bool) or bid<1:return jsonify({'error':'Valid book_id required'}),400
        with db() as c:
            if not c.execute('SELECT 1 FROM books WHERE id=?',(bid,)).fetchone():return jsonify({'error':'Book not found'}),404
            if c.execute("SELECT 1 FROM book_reservations WHERE user_id=? AND book_id=? AND status IN ('queued','ready')",(u['id'],bid)).fetchone():return jsonify({'error':'An active reservation already exists for this book'}),409
            if branch_id is not None and not c.execute("SELECT 1 FROM library_branches WHERE id=? AND status='active'",(branch_id,)).fetchone():return jsonify({'error':'Active branch not found'}),400
            try:
                cur=c.execute("INSERT INTO book_reservations(user_id,book_id,branch_id,status) VALUES(?,?,?,'queued')",(u['id'],bid,branch_id))
            except sqlite3.IntegrityError:return jsonify({'error':'An active reservation already exists for this book'}),409
            position=c.execute("SELECT COUNT(*) FROM book_reservations WHERE book_id=? AND status='queued' AND id<=?",(bid,cur.lastrowid)).fetchone()[0]
            c.execute('UPDATE book_reservations SET queue_position=? WHERE id=?',(position,cur.lastrowid))
        return jsonify({'ok':True,'reservation_id':cur.lastrowid,'queue_position':position}),201

    @app.patch('/api/admin/reservations/<int:reservation_id>')
    def api_reservation_update(reservation_id):
        u,err=actor()
        if err:return err
        if not staff(u):return jsonify({'error':'Library staff access required'}),403
        b=request.get_json(silent=True) or {}; status=b.get('status')
        if status not in ('queued','ready','fulfilled','cancelled'):return jsonify({'error':'Invalid reservation status'}),400
        with db() as c:
            cur=c.execute('UPDATE book_reservations SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(status,reservation_id))
            if not cur.rowcount:return jsonify({'error':'Reservation not found'}),404
        return jsonify({'ok':True,'id':reservation_id,'status':status})

    @app.get('/api/admin/branches')
    def api_branches_list():
        u,err=actor()
        if err:return err
        if not staff(u):return jsonify({'error':'Library staff access required'}),403
        with db() as c:rows=c.execute('SELECT br.*,COUNT(bi.book_id) catalog_titles FROM library_branches br LEFT JOIN branch_inventory bi ON bi.branch_id=br.id GROUP BY br.id ORDER BY br.name').fetchall()
        return jsonify({'items':[dict(r) for r in rows]})

    @app.post('/api/admin/branches')
    def api_branch_create():
        u,err=actor()
        if err:return err
        if not admin(u):return jsonify({'error':'Administrator access required'}),403
        b=request.get_json(silent=True) or {}; name=str(b.get('name','')).strip()[:100]; code=str(b.get('code','')).strip().upper()[:12]; city=str(b.get('city','')).strip()[:80]; address=str(b.get('address','')).strip()[:240]; phone=str(b.get('phone','')).strip()[:32]
        if not name or not code or not code.isalnum():return jsonify({'error':'Branch name and alphanumeric code are required'}),400
        try:
            with db() as c:cur=c.execute('INSERT INTO library_branches(name,code,city,address,phone) VALUES(?,?,?,?,?)',(name,code,city,address,phone))
        except sqlite3.IntegrityError:return jsonify({'error':'Branch name or code already exists'}),409
        return jsonify({'ok':True,'id':cur.lastrowid}),201

    @app.patch('/api/admin/branches/<int:branch_id>')
    def api_branch_update(branch_id):
        u,err=actor()
        if err:return err
        if not admin(u):return jsonify({'error':'Administrator access required'}),403
        b=request.get_json(silent=True) or {}; status=b.get('status'); name=b.get('name')
        if status not in (None,'active','inactive') or (name is not None and (not isinstance(name,str) or not name.strip() or len(name)>100)):return jsonify({'error':'Invalid branch update'}),400
        with db() as c:
            row=c.execute('SELECT id FROM library_branches WHERE id=?',(branch_id,)).fetchone()
            if not row:return jsonify({'error':'Branch not found'}),404
            if status is not None:c.execute('UPDATE library_branches SET status=? WHERE id=?',(status,branch_id))
            if name is not None:c.execute('UPDATE library_branches SET name=? WHERE id=?',(name.strip(),branch_id))
        return jsonify({'ok':True,'id':branch_id})

    @app.get('/api/admin/branches/<int:branch_id>/inventory')
    def api_branch_inventory_list(branch_id):
        u,err=actor()
        if err:return err
        if not staff(u):return jsonify({'error':'Library staff access required'}),403
        with db() as c:
            if not c.execute('SELECT 1 FROM library_branches WHERE id=?',(branch_id,)).fetchone():return jsonify({'error':'Branch not found'}),404
            rows=c.execute('SELECT bi.book_id,b.title,b.author,bi.copies FROM branch_inventory bi JOIN books b ON b.id=bi.book_id WHERE bi.branch_id=? ORDER BY b.title',(branch_id,)).fetchall()
        return jsonify({'items':[dict(r) for r in rows]})

    @app.put('/api/admin/branches/<int:branch_id>/inventory')
    def api_branch_inventory_update(branch_id):
        u,err=actor()
        if err:return err
        if not admin(u):return jsonify({'error':'Administrator access required'}),403
        b=request.get_json(silent=True) or {}; bid=b.get('book_id'); copies=b.get('copies')
        if not isinstance(bid,int) or isinstance(bid,bool) or bid<1 or not isinstance(copies,int) or isinstance(copies,bool) or not 0<=copies<=100000:return jsonify({'error':'Valid book_id and copies (0..100000) required'}),400
        with db() as c:
            if not c.execute('SELECT 1 FROM library_branches WHERE id=?',(branch_id,)).fetchone():return jsonify({'error':'Branch not found'}),404
            if not c.execute('SELECT 1 FROM books WHERE id=?',(bid,)).fetchone():return jsonify({'error':'Book not found'}),404
            c.execute('INSERT INTO branch_inventory(branch_id,book_id,copies) VALUES(?,?,?) ON CONFLICT(branch_id,book_id) DO UPDATE SET copies=excluded.copies',(branch_id,bid,copies))
        return jsonify({'ok':True,'branch_id':branch_id,'book_id':bid,'copies':copies})

    @app.post('/api/reader/sessions/start')
    def api_reader_session_start():
        u,err=actor()
        if err:return err
        b=request.get_json(silent=True) or {}; bid=b.get('book_id')
        if not isinstance(bid,int) or isinstance(bid,bool) or bid<1:return jsonify({'error':'Valid book_id required'}),400
        with db() as c:
            book=c.execute('SELECT id,genre FROM books WHERE id=?',(bid,)).fetchone()
            if not book:return jsonify({'error':'Book not found'}),404
            active=c.execute('SELECT id FROM library_reading_sessions WHERE user_id=? AND ended_at IS NULL ORDER BY id DESC LIMIT 1',(u['id'],)).fetchone()
            if active:return jsonify({'error':'A reading session is already active','session_id':active['id']}),409
            cur=c.execute('INSERT INTO library_reading_sessions(user_id,book_id,started_at,genre) VALUES(?,?,?,?)',(u['id'],bid,datetime.now(timezone.utc).isoformat(),book['genre'] or 'Uncategorized'))
        return jsonify({'ok':True,'session_id':cur.lastrowid}),201

    @app.post('/api/reader/sessions/<int:session_id>/stop')
    def api_reader_session_stop(session_id):
        u,err=actor()
        if err:return err
        with db() as c:
            c.execute('BEGIN IMMEDIATE'); row=c.execute('SELECT * FROM library_reading_sessions WHERE id=? AND user_id=?',(session_id,u['id'])).fetchone()
            if not row:return jsonify({'error':'Reading session not found'}),404
            if row['ended_at']:return jsonify({'ok':True,'seconds':row['seconds'],'already_stopped':True})
            start=datetime.fromisoformat(row['started_at']); elapsed=max(0,min(8*3600,int((datetime.now(timezone.utc)-start).total_seconds())))
            c.execute('UPDATE library_reading_sessions SET ended_at=?,seconds=? WHERE id=?',(datetime.now(timezone.utc).isoformat(),elapsed,session_id))
        return jsonify({'ok':True,'seconds':elapsed})

    @app.get('/api/reader/analytics')
    def api_reader_analytics():
        u,err=actor()
        if err:return err
        with db() as c:
            daily=c.execute("SELECT date(started_at) day,SUM(seconds) seconds,COUNT(*) sessions FROM library_reading_sessions WHERE user_id=? AND started_at>=date('now','-29 days') GROUP BY date(started_at) ORDER BY day",(u['id'],)).fetchall()
            genres=c.execute("SELECT genre,SUM(seconds) seconds,COUNT(*) sessions FROM library_reading_sessions WHERE user_id=? AND ended_at IS NOT NULL GROUP BY genre ORDER BY seconds DESC",(u['id'],)).fetchall()
        return jsonify({'daily':[dict(r) for r in daily],'genres':[dict(r) for r in genres],'total_seconds':sum(r['seconds'] for r in daily)})
