"""Authenticated reader workspace APIs for LibraAI dashboard modules."""
from flask import Blueprint, jsonify, request
from datetime import datetime
import sqlite3


def install_dashboard_workspace(app, db, current_user):
    bp = Blueprint('dashboard_workspace', __name__)

    def signed_in():
        user = current_user()
        if not user:
            return None, (jsonify({'error': 'Sign in required', 'code': 'auth_required'}), 401)
        return user, None

    def setup(conn):
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS libra_reading_goals (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, title TEXT NOT NULL,
          target_books INTEGER NOT NULL DEFAULT 1, completed_books INTEGER NOT NULL DEFAULT 0,
          period TEXT NOT NULL DEFAULT 'Monthly', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS libra_goal_posts (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, goal_id INTEGER,
          body TEXT NOT NULL CHECK(length(body)<=1200), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS libra_guilds (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT NOT NULL DEFAULT '',
          level INTEGER NOT NULL DEFAULT 1 CHECK(level BETWEEN 1 AND 10),
          created_by INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS libra_guild_members (
          guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
          joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(guild_id,user_id)
        );
        CREATE TABLE IF NOT EXISTS libra_wallet_ledger (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, kind TEXT NOT NULL,
          amount REAL NOT NULL, description TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS libra_quiz_attempts (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, game TEXT NOT NULL,
          correct INTEGER NOT NULL DEFAULT 0, coins INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        # Seed discoverable guilds once, without overwriting user-created records.
        if conn.execute('SELECT COUNT(*) FROM libra_guilds').fetchone()[0] == 0:
            conn.executemany('INSERT OR IGNORE INTO libra_guilds(name,description,level,created_by) VALUES(?,?,?,?)', [
                ('Future Readers', 'Technology, AI and tomorrow’s ideas.', 8, 0),
                ('Mystery Circle', 'Mystery, thriller and plot-twist lovers.', 6, 0),
                ('Bangla Book Club', 'Bangla literature, poetry and modern voices.', 5, 0),
                ('Mindful Pages', 'Personal growth and thoughtful reading.', 4, 0),
            ])

    @bp.get('/api/dashboard/summary')
    def summary():
        user, error = signed_in()
        if error: return error
        with db() as conn:
            setup(conn)
            progress = [dict(r) for r in conn.execute('''SELECT p.book_id,p.page,p.percent,p.updated,b.title,b.author,b.format
                FROM progress p JOIN books b ON b.id=p.book_id WHERE p.user_id=? ORDER BY p.updated DESC''', (user['id'],))]
            completed = sum(1 for p in progress if float(p.get('percent') or 0) >= 100)
            wishlist = conn.execute('SELECT COUNT(*) FROM wishlist WHERE user_id=?', (user['id'],)).fetchone()[0]
            wishlist_items = [dict(r) for r in conn.execute('SELECT b.id,b.title,b.author,b.price FROM wishlist w JOIN books b ON b.id=w.book_id WHERE w.user_id=? ORDER BY w.id DESC LIMIT 30',(user['id'],))]
            cart = conn.execute('SELECT COUNT(*) FROM cart WHERE user_id=?', (user['id'],)).fetchone()[0]
            cart_items = [dict(r) for r in conn.execute('SELECT b.id,b.title,b.author,b.price,c.qty,c.format FROM cart c JOIN books b ON b.id=c.book_id WHERE c.user_id=? ORDER BY c.id DESC LIMIT 30',(user['id'],))]
            try:
                books_purchased = conn.execute("SELECT COALESCE(SUM(oi.quantity),0) FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE o.user_id=? AND lower(COALESCE(o.status,'')) NOT IN ('cancelled','failed')", (user['id'],)).fetchone()[0]
            except sqlite3.Error:
                books_purchased = 0
            order_row = conn.execute("SELECT COUNT(*) count,COALESCE(SUM(total),0) spent FROM orders WHERE user_id=? AND lower(COALESCE(status,'')) NOT IN ('cancelled','failed')", (user['id'],)).fetchone()
            guilds = [dict(r) for r in conn.execute('''SELECT g.id,g.name,g.level,COUNT(m.user_id) members FROM libra_guilds g
                JOIN libra_guild_members m ON m.guild_id=g.id WHERE m.user_id=? GROUP BY g.id,g.name,g.level''', (user['id'],))]
            top_guilds = [dict(r) for r in conn.execute('''SELECT g.id,g.name,g.level,COUNT(m.user_id) members FROM libra_guilds g
                LEFT JOIN libra_guild_members m ON m.guild_id=g.id GROUP BY g.id,g.name,g.level ORDER BY members DESC,g.id ASC LIMIT 5''')]
            coins = conn.execute('SELECT COALESCE(SUM(amount),0) FROM libra_wallet_ledger WHERE user_id=? AND kind="coin"', (user['id'],)).fetchone()[0]
            goals = [dict(r) for r in conn.execute('SELECT * FROM libra_reading_goals WHERE user_id=? ORDER BY id DESC', (user['id'],))]
            refund_total = 0
            try:
                refund_total = conn.execute("SELECT COALESCE(SUM(r.amount_cents),0)/100.0 FROM refund_requests r JOIN orders o ON o.id=r.order_id WHERE o.user_id=? AND r.state='refunded'", (user['id'],)).fetchone()[0]
            except sqlite3.Error:
                pass
        role = str(user['role'] or 'reader').lower()
        return jsonify({'user': {'id': user['id'], 'name': user['name'], 'username': user['username'], 'email': user['email'], 'role': role, 'plan': user['plan'] or 'Free'},
            'stats': {'books_started': len(progress), 'books_completed': completed, 'reading_minutes': 0, 'wishlist_count': wishlist, 'cart_count': cart,
                      'orders_count': order_row['count'], 'books_purchased': int(books_purchased or 0), 'spent': round(float(order_row['spent'] or 0),2), 'refunds': round(float(refund_total or 0),2),
                      'coins': int(coins or 0), 'network_count': len(guilds)}, 'progress': progress, 'wishlist': wishlist_items, 'cart_items': cart_items, 'goals': goals, 'guilds': guilds, 'top_guilds': top_guilds})

    @bp.get('/api/dashboard/goals')
    def goals():
        user, error = signed_in()
        if error: return error
        with db() as conn:
            setup(conn)
            rows = conn.execute('''SELECT p.id,p.body,p.created_at,u.name,u.username FROM libra_goal_posts p
                JOIN users u ON u.id=p.user_id ORDER BY p.id DESC LIMIT 60''').fetchall()
            own = conn.execute('SELECT * FROM libra_reading_goals WHERE user_id=? ORDER BY id DESC', (user['id'],)).fetchall()
        return jsonify({'posts':[dict(r) for r in rows], 'goals':[dict(r) for r in own]})

    @bp.post('/api/dashboard/goals')
    def create_goal_post():
        user, error = signed_in()
        if error: return error
        body = str((request.get_json(silent=True) or {}).get('body','')).strip()[:1200]
        if len(body) < 3: return jsonify({'error':'Write at least 3 characters.'}), 400
        with db() as conn:
            setup(conn)
            conn.execute('INSERT INTO libra_goal_posts(user_id,body) VALUES(?,?)', (user['id'],body))
        return jsonify({'ok':True}), 201

    @bp.get('/api/dashboard/guilds')
    def guilds():
        user, error = signed_in()
        if error: return error
        q = str(request.args.get('q','')).strip()[:80]
        level = request.args.get('level','')
        with db() as conn:
            setup(conn)
            rows = conn.execute('''SELECT g.id,g.name,g.description,g.level,g.created_at,COUNT(m.user_id) members,
                MAX(CASE WHEN mine.user_id=? THEN 1 ELSE 0 END) joined
                FROM libra_guilds g LEFT JOIN libra_guild_members m ON m.guild_id=g.id
                LEFT JOIN libra_guild_members mine ON mine.guild_id=g.id AND mine.user_id=?
                WHERE (?='' OR g.name LIKE ?) AND (?='' OR g.level=?)
                GROUP BY g.id ORDER BY members DESC,g.id DESC''', (user['id'],user['id'],q,'%'+q+'%',level,level)).fetchall()
        return jsonify([dict(r) for r in rows])

    @bp.post('/api/dashboard/guilds')
    def create_guild():
        user, error = signed_in()
        if error: return error
        data = request.get_json(silent=True) or {}
        name = str(data.get('name','')).strip()[:80]
        description = str(data.get('description','')).strip()[:500]
        if len(name) < 3: return jsonify({'error':'Community name must be at least 3 characters.'}), 400
        with db() as conn:
            setup(conn)
            try:
                cur = conn.execute('INSERT INTO libra_guilds(name,description,level,created_by) VALUES(?,?,1,?)', (name,description,user['id']))
            except sqlite3.IntegrityError:
                return jsonify({'error':'A community with this name already exists.'}), 409
            gid = cur.lastrowid
            conn.execute('INSERT INTO libra_guild_members(guild_id,user_id) VALUES(?,?)', (gid,user['id']))
        return jsonify({'ok':True,'id':gid}), 201

    @bp.post('/api/dashboard/guilds/<int:guild_id>/join')
    def join_guild(guild_id):
        user, error = signed_in()
        if error: return error
        with db() as conn:
            setup(conn)
            if not conn.execute('SELECT 1 FROM libra_guilds WHERE id=?',(guild_id,)).fetchone(): return jsonify({'error':'Community not found.'}),404
            conn.execute('INSERT OR IGNORE INTO libra_guild_members(guild_id,user_id) VALUES(?,?)',(guild_id,user['id']))
        return jsonify({'ok':True})

    @bp.get('/api/dashboard/wallet')
    def wallet():
        user, error = signed_in()
        if error: return error
        with db() as conn:
            setup(conn)
            orders = [dict(r) for r in conn.execute('''SELECT o.id,o.total,o.status,o.created,COALESCE(SUM(oi.quantity),0) item_count,
                GROUP_CONCAT(DISTINCT oi.title_snapshot) titles FROM orders o LEFT JOIN order_items oi ON oi.order_id=o.id
                WHERE o.user_id=? GROUP BY o.id ORDER BY o.id DESC LIMIT 50''',(user['id'],))]
            ledger = [dict(r) for r in conn.execute('SELECT kind,amount,description,created_at FROM libra_wallet_ledger WHERE user_id=? ORDER BY id DESC LIMIT 50',(user['id'],))]
            try:
                refunds = [dict(r) for r in conn.execute("SELECT r.id,r.amount_cents/100.0 amount,r.state,r.reason,r.created,o.id order_id FROM refund_requests r JOIN orders o ON o.id=r.order_id WHERE o.user_id=? ORDER BY r.id DESC LIMIT 50",(user['id'],))]
            except sqlite3.Error:
                refunds = []
        return jsonify({'orders':orders,'ledger':ledger,'refunds':refunds})

    @bp.get('/api/dashboard/vault')
    def vault():
        user, error = signed_in()
        if error: return error
        with db() as conn:
            setup(conn)
            coins = conn.execute('SELECT COALESCE(SUM(amount),0) FROM libra_wallet_ledger WHERE user_id=? AND kind="coin"',(user['id'],)).fetchone()[0]
            attempts = conn.execute('SELECT COUNT(*),COALESCE(SUM(correct),0) FROM libra_quiz_attempts WHERE user_id=?',(user['id'],)).fetchone()
        return jsonify({'coins':int(coins or 0),'attempts':attempts[0],'correct':attempts[1]})

    @bp.post('/api/dashboard/vault/quiz')
    def quiz_attempt():
        user, error = signed_in()
        if error: return error
        data = request.get_json(silent=True) or {}
        game = str(data.get('game','Quick Quiz'))[:60]
        # Grade the answer on the server; never trust a client-supplied `correct` flag.
        answer = data.get('answer')
        expected = {'Book Knowledge Quiz': 1, 'Memory Match': 0}.get(game)
        correct = expected is not None and type(answer) is int and answer == expected
        with db() as conn:
            setup(conn)
            daily = conn.execute("SELECT COUNT(*) FROM libra_quiz_attempts WHERE user_id=? AND created_at>=date('now')",(user['id'],)).fetchone()[0]
            coins = 5 if correct and daily < 20 else 0
            conn.execute('INSERT INTO libra_quiz_attempts(user_id,game,correct,coins) VALUES(?,?,?,?)',(user['id'],game,int(correct),coins))
            if coins: conn.execute('INSERT INTO libra_wallet_ledger(user_id,kind,amount,description) VALUES(?,?,?,?)',(user['id'],'coin',coins,'Reward: '+game))
        return jsonify({'ok':True,'is_correct':correct,'coins_earned':coins,'daily_attempt_limit_reached':daily>=20})

    app.register_blueprint(bp)
