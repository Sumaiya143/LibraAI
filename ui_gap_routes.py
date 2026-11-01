"""Premium, server-rendered UI for existing LibraAI API-only/partial workflows.

All mutations use normal Flask forms protected by the app-wide CSRF middleware.
External payouts/refunds are deliberately not simulated as completed money movement.
"""
from datetime import date
from urllib.parse import urlencode
from decimal import Decimal, InvalidOperation
import secrets
from flask import Blueprint, request, redirect, abort, flash
from markupsafe import escape

ui_gap_bp = Blueprint('ui_gap', __name__)


def _ctx():
    from app import db, current_user, page
    u = current_user()
    if not u:
        return None, db, page
    return u, db, page


def _require(roles=None):
    from app import current_user, abort
    u = current_user()
    if not u:
        abort(401)
    if roles and u['role'] not in roles:
        abort(403)
    return u


def _status(value):
    s = str(value or 'unknown').lower()
    cls = 'good' if s in ('accepted','approved','paid','delivered','completed','active') else ('warn' if s in ('waiting','offered','requested','pending','created') else 'quiet')
    return f'<span class="pill {cls}">{escape(str(value or "Unknown").title())}</span>'


def _layout_css():
    return '''<style>
.gap-hero{position:relative;overflow:hidden;padding:30px;border-radius:24px;color:#fff;background:radial-gradient(circle at 82% 18%,rgba(88,213,255,.45),transparent 27%),linear-gradient(118deg,#201c80 0%,#5145e8 48%,#8d65ff 100%);box-shadow:0 18px 45px #4435c426;margin-bottom:22px}
.gap-hero:after{content:"";position:absolute;width:230px;height:230px;border:1px solid #ffffff35;border-radius:50%;right:-60px;top:-95px;box-shadow:0 0 0 22px #ffffff0d,0 0 0 46px #ffffff0a;pointer-events:none}
.gap-hero h1{font-size:clamp(27px,3vw,39px);letter-spacing:-1px;margin:8px 0}.gap-hero p{max-width:720px;color:#f2f2ff;margin:8px 0 0;line-height:1.65}.gap-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(235px,1fr));gap:16px;margin:16px 0}.gap-card{background:linear-gradient(145deg,#fff,#fbfaff);border:1px solid #e4e6ff;border-radius:18px;padding:18px;box-shadow:0 10px 26px #3945a20b;transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease;min-width:0}.gap-card:hover{transform:translateY(-3px);box-shadow:0 16px 34px #4435c41c;border-color:#c7c4ff}.gap-card h2,.gap-card h3{margin:0 0 8px}.gap-card p{line-height:1.55}.gap-kpi{font-size:28px;font-weight:850;letter-spacing:-.7px;color:#4338ca}.gap-muted{color:#707b98}.gap-form{display:grid;gap:9px}.gap-form label{font-size:13px;font-weight:700;color:#4b5573}.gap-form .input,.gap-form select,.gap-form textarea{margin:0;background:#fff}.gap-pill{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:99px;background:#f0efff;color:#4d42c8;font-size:12px;font-weight:750}.gap-table-wrap{overflow:auto;border:1px solid #e5e8f4;border-radius:16px;background:#fff}.gap-table{width:100%;border-collapse:collapse;min-width:620px}.gap-table th,.gap-table td{padding:13px 15px;border-bottom:1px solid #edf0f7;text-align:left;font-size:13px;vertical-align:top}.gap-table th{background:#f6f6ff;color:#535d7c;font-size:11px;text-transform:uppercase;letter-spacing:.06em}.gap-table tr:last-child td{border-bottom:0}.pill.good{background:#dcfbf0;color:#087d5d}.pill.warn{background:#fff4d7;color:#966100}.pill.quiet{background:#eef1f8;color:#63708b}.gap-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.gap-note{padding:13px 15px;border-radius:14px;background:#f0f4ff;border:1px solid #dfe6ff;color:#4e5c84;font-size:13px;line-height:1.55}.gap-empty{padding:28px;text-align:center;border:1px dashed #cdd3ee;border-radius:16px;color:#74809c;background:#fafaff}.gap-section{margin:22px 0}.gap-small{font-size:12px}.gap-btn-danger{background:#fff0f2;color:#b42340}.gap-statrow{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:15px 0}.gap-stat{padding:15px;border:1px solid #e4e7fb;border-radius:15px;background:linear-gradient(135deg,#fff,#f5f4ff)}
body.midnight .gap-card,body.midnight .gap-stat,body.midnight .gap-table-wrap{background:linear-gradient(145deg,#101a36,#172247);border-color:#29375f;color:var(--ink)}body.midnight .gap-table th{background:#202b50;color:#c9d5f3}body.midnight .gap-table td{border-color:#29375f}body.midnight .gap-form label{color:#c4cdec}body.midnight .gap-form .input,body.midnight .gap-form select,body.midnight .gap-form textarea{background:#111b37;color:#eef2ff;border-color:#35446e}body.midnight .gap-note{background:#1a2850;color:#cbd7ff;border-color:#344578}body.midnight .gap-stat{background:#111b37}body.midnight .gap-empty{background:#111b37;border-color:#344578;color:#bdc8e7}
@media(max-width:650px){.gap-hero{padding:22px}.gap-table{min-width:560px}.gap-card{padding:15px}}
@media(prefers-reduced-motion:reduce){.gap-card{transition:none}}
</style>'''


def _page(title, body, **ctx):
    from app import page
    return page(title, _layout_css() + body, **ctx)


@ui_gap_bp.get('/my/waitlist')
def my_waitlist():
    u, db, _ = _ctx()
    if not u: return redirect('/login')
    with db() as c:
        rows = c.execute('''SELECT w.id,w.book_id,b.title,b.author,w.status,w.joined_at,w.expires_at
            FROM book_waitlist w JOIN books b ON b.id=w.book_id WHERE w.user_id=? ORDER BY w.id DESC''',(u['id'],)).fetchall()
        books = c.execute('SELECT id,title,author,stock FROM books ORDER BY title').fetchall()
    items = ''.join(f'''<tr><td><b>{escape(r['title'])}</b><div class="gap-muted gap-small">{escape(r['author'] or '')}</div></td><td>{_status(r['status'])}</td><td>{escape((r['joined_at'] or '')[:10])}</td><td>{escape((r['expires_at'] or '—')[:10] if r['expires_at'] else '—')}</td><td><div class="gap-actions">'''+(f'''<form method="post" action="/my/waitlist/{r['id']}/accept"><button class="btn green">Accept offer</button></form>''' if r['status']=='offered' else '')+(f'''<form method="post" action="/my/waitlist/{r['id']}/cancel"><button class="btn ghost gap-btn-danger">Cancel</button></form>''' if r['status'] in ('waiting','offered') else '')+'''</div></td></tr>''' for r in rows)
    opts=''.join(f'<option value="{b["id"]}">{escape(b["title"])} — {escape(b["author"] or "Unknown author")}</option>' for b in books)
    body=f'''<section class="gap-hero"><span class="gap-pill">📚 Library queue</span><h1>Your reading, next in line.</h1><p>Track reservations and waitlist offers in one place. Offers may expire, so check the status and expiry date before accepting.</p><div class="gap-actions" style="margin-top:18px"><a class="btn" href="/discover">Explore catalog →</a><a class="btn ghost" href="/library">My Library</a></div></section>
    <div class="gap-statrow"><div class="gap-stat"><div class="gap-muted gap-small">Total entries</div><div class="gap-kpi">{len(rows)}</div></div><div class="gap-stat"><div class="gap-muted gap-small">Waiting</div><div class="gap-kpi">{sum(1 for r in rows if r['status']=='waiting')}</div></div><div class="gap-stat"><div class="gap-muted gap-small">Offers to act on</div><div class="gap-kpi">{sum(1 for r in rows if r['status']=='offered')}</div></div></div>
    <section class="gap-card"><h2>Join a waitlist</h2><p class="gap-muted">Choose a book to join its queue. Duplicate active entries are prevented by the waitlist engine.</p><form class="gap-form" method="post" action="/my/waitlist/join"><label for="book_id">Book</label><select class="input" id="book_id" name="book_id" required><option value="">Select a title…</option>{opts}</select><button class="btn" type="submit">Join waitlist</button></form></section>
    <section class="gap-section"><div class="row between"><h2>My waitlist activity</h2><a href="/my-alerts">Alerts & saved searches →</a></div>{'<div class="gap-table-wrap"><table class="gap-table"><thead><tr><th>Book</th><th>Status</th><th>Joined</th><th>Offer expires</th><th>Actions</th></tr></thead><tbody>'+items+'</tbody></table></div>' if rows else '<div class="gap-empty"><h3>No waitlist entries yet</h3><p>Join a queue above to track your place here.</p></div>'}</section>'''
    return _page('My Waitlist',body)


@ui_gap_bp.post('/my/waitlist/join')
def join_waitlist_form():
    u=_require()
    from app import db
    from waitlist_engine import join, WaitlistError
    try: bid=int(request.form.get('book_id','0'))
    except ValueError: abort(400)
    try:
        with db() as c: join(c,u['id'],bid)
    except WaitlistError as e: flash(str(e))
    else: flash('You joined the waitlist.')
    return redirect('/my/waitlist')


@ui_gap_bp.post('/my/waitlist/<int:entry_id>/cancel')
def cancel_waitlist_form(entry_id):
    u=_require()
    from app import db
    from waitlist_engine import cancel, WaitlistError
    try:
        with db() as c: cancel(c,u['id'],entry_id)
    except WaitlistError as e: flash(str(e))
    else: flash('Waitlist entry cancelled.')
    return redirect('/my/waitlist')


@ui_gap_bp.post('/my/waitlist/<int:entry_id>/accept')
def accept_waitlist_form(entry_id):
    u=_require()
    from app import db
    from waitlist_engine import accept, WaitlistError
    try:
        with db() as c: accept(c,u['id'],entry_id)
    except WaitlistError as e: flash(str(e))
    else: flash('Offer accepted. Library staff must confirm collection or loan.')
    return redirect('/my/waitlist')


@ui_gap_bp.route('/admin/waitlist', methods=['GET','POST'])
def admin_waitlist():
    u=_require({'admin'})
    from app import db
    from waitlist_engine import offer_next, WaitlistError
    if request.method=='POST':
        try: bid=int(request.form.get('book_id','0')); days=int(request.form.get('days','2'))
        except ValueError: abort(400)
        try:
            with db() as c: entry_id=offer_next(c,bid,days)
        except WaitlistError as e: flash(str(e))
        else: flash('Offer sent to next reader.' if entry_id else 'No reader is waiting for this book.')
        return redirect('/admin/waitlist')
    with db() as c:
        rows=c.execute('''SELECT w.id,w.status,w.joined_at,w.expires_at,u.name AS reader,b.title,b.id AS book_id
          FROM book_waitlist w JOIN users u ON u.id=w.user_id JOIN books b ON b.id=w.book_id ORDER BY CASE w.status WHEN 'offered' THEN 0 WHEN 'waiting' THEN 1 ELSE 2 END,w.joined_at''').fetchall()
        books=c.execute('SELECT id,title FROM books ORDER BY title').fetchall()
    items=''.join(f'<tr><td><b>{escape(r["title"])}</b><div class="gap-muted gap-small">Book #{r["book_id"]}</div></td><td>{escape(r["reader"] or "Reader")}</td><td>{_status(r["status"])}</td><td>{escape((r["joined_at"] or "")[:10])}</td><td>{escape((r["expires_at"] or "—")[:10] if r["expires_at"] else "—")}</td></tr>' for r in rows)
    opts=''.join(f'<option value="{b["id"]}">{escape(b["title"])}</option>' for b in books)
    body=f'''<section class="gap-hero"><span class="gap-pill">⚙ Admin workspace</span><h1>Waitlist operations</h1><p>Review the queue and issue an offer to the next waiting reader. Offer expiry and FIFO ordering are handled by the existing waitlist engine.</p></section><section class="gap-card"><h2>Offer next reader</h2><form class="gap-form" method="post"><label>Book</label><select class="input" name="book_id" required>{opts}</select><label>Offer validity</label><select class="input" name="days"><option value="2">2 days</option><option value="1">1 day</option><option value="3">3 days</option><option value="7">7 days</option><option value="14">14 days</option></select><button class="btn">Issue offer</button></form></section><section class="gap-section"><h2>Queue overview</h2>{'<div class="gap-table-wrap"><table class="gap-table"><thead><tr><th>Book</th><th>Reader</th><th>Status</th><th>Joined</th><th>Expires</th></tr></thead><tbody>'+items+'</tbody></table></div>' if rows else '<div class="gap-empty">No waitlist entries have been created yet.</div>'}</section>'''
    return _page('Waitlist Operations',body)


@ui_gap_bp.get('/saved-searches')
def saved_searches_page():
    u, db, _ = _ctx()
    if not u: return redirect('/login')
    with db() as c:
        searches=c.execute('SELECT * FROM saved_searches WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall()
        alerts=c.execute('SELECT * FROM inbox_alerts WHERE user_id=? ORDER BY id DESC LIMIT 30',(u['id'],)).fetchall()
    items=''.join(f'''<div class="gap-card"><div class="row between"><span class="gap-pill">⌕ Saved search</span><form method="post" action="/saved-searches/{s['id']}/delete"><button class="btn ghost gap-btn-danger">Remove</button></form></div><h3 style="margin-top:12px">{escape(s['phrase'])}</h3><p class="gap-muted">{escape(s['genre'] or 'All genres')} · Created {(s['created'] or '')[:10]}</p><a class="btn ghost" href="/discover?{escape(urlencode({'q': s['phrase'], 'genre': s['genre'] or ''}))}">Run search →</a></div>''' for s in searches)
    alert_html=''.join(f'<div class="gap-card"><div class="row between"><b>{escape(a["subject"])}</b>{_status("New" if not a["read_at"] else "Read")}</div><p>{escape(a["message"])}</p><div class="gap-muted gap-small">{escape((a["created"] or "")[:16])}</div>'+ (f'<form method="post" action="/my-alerts/{a["id"]}/read"><button class="btn ghost">Mark as read</button></form>' if not a['read_at'] else '')+'</div>' for a in alerts)
    body=f'''<section class="gap-hero"><span class="gap-pill">🔔 Personal discovery</span><h1>Saved searches & alerts</h1><p>Keep useful catalog searches close and see matching-book notifications when supported catalog workflows add a new title.</p></section><div class="gap-grid"><section class="gap-card"><h2>Create a saved search</h2><form class="gap-form" method="post" action="/saved-searches"><label>Title, author or ISBN</label><input class="input" name="phrase" maxlength="120" minlength="2" placeholder="e.g. Atomic Habits or James Clear" required><label>Genre (optional)</label><input class="input" name="genre" maxlength="60" placeholder="e.g. Self Development"><button class="btn">Save search</button></form></section><section class="gap-card"><h2>How alerts work</h2><p class="gap-muted">Saved searches are matched when supported catalog insertion workflows call the alert service. This is not a continuous external-web monitoring service.</p><a href="/my-alerts">Open legacy alerts view →</a></section></div><section class="gap-section"><h2>Saved searches <span class="gap-pill">{len(searches)}</span></h2>{'<div class="gap-grid">'+items+'</div>' if searches else '<div class="gap-empty">No saved searches yet. Save one above to revisit it quickly.</div>'}</section><section class="gap-section"><h2>Recent alerts <span class="gap-pill">{len(alerts)}</span></h2>{'<div class="gap-grid">'+alert_html+'</div>' if alerts else '<div class="gap-empty">No alerts yet. Matching titles will appear here when detected.</div>'}</section>'''
    return _page('Saved Searches',body)


@ui_gap_bp.get('/learning/planner')
def learning_planner_page():
    u, db, _ = _ctx()
    if not u: return redirect('/login')
    with db() as c:
        goals=c.execute('SELECT * FROM learning_goals WHERE user_id=? ORDER BY deadline',(u['id'],)).fetchall()
        cards=c.execute('SELECT f.*,b.title FROM flashcards f JOIN books b ON b.id=f.book_id WHERE f.user_id=? AND f.due<=? ORDER BY f.due LIMIT 30',(u['id'],date.today().isoformat())).fetchall()
    goals_html=''.join(f'''<div class="gap-card"><div class="row between"><span class="gap-pill">🎯 Learning goal</span><span class="gap-muted gap-small">Due {escape(g['deadline'])}</span></div><h3 style="margin-top:12px">{escape(g['title'])}</h3><div class="row between"><b>{g['current_pages']} / {g['target_pages']} pages</b><span class="gap-muted gap-small">{min(100,int(g['current_pages']*100/max(1,g['target_pages'])))}%</span></div><div class="bar"><i style="width:{min(100,int(g['current_pages']*100/max(1,g['target_pages'])))}%"></i></div><form class="gap-form" style="margin-top:12px" method="post" action="/learning/goals/{g['id']}/progress"><label>Log pages read</label><input class="input" type="number" min="1" max="500" name="pages" value="10" required><button class="btn ghost">Update progress</button></form></div>''' for g in goals)
    cards_html=''.join(f'''<div class="gap-card"><span class="gap-pill">🧠 Review card</span><h3 style="margin-top:12px">{escape(x['title'])}</h3><p><b>{escape(x['front'])}</b></p><details><summary>Reveal answer</summary><p>{escape(x['back'])}</p></details><form class="gap-form" method="post" action="/learning/cards/{x['id']}/review"><label>Recall quality (0–5)</label><select class="input" name="grade">{''.join(f'<option value="{i}">{i}</option>' for i in range(6))}</select><button class="btn">Save review</button></form></div>''' for x in cards)
    body=f'''<section class="gap-hero"><span class="gap-pill">✨ Personal learning system</span><h1>Plan less. Learn consistently.</h1><p>Set measurable reading goals, track progress and review due flashcards with the existing spaced-repetition scheduler.</p><div class="gap-actions" style="margin-top:18px"><a class="btn" href="/study">Open study tools →</a><a class="btn ghost" href="/learning/">Classic learning studio</a></div></section><div class="gap-grid"><section class="gap-card"><h2>Create a goal</h2><form class="gap-form" method="post" action="/learning/goals"><label>Goal name</label><input class="input" name="title" maxlength="120" placeholder="Read 100 pages this month" required><label>Target pages</label><input class="input" type="number" name="target_pages" min="1" max="100000" required><label>Deadline</label><input class="input" type="date" name="deadline" min="{date.today().isoformat()}" required><button class="btn">Create learning goal</button></form></section><section class="gap-card"><h2>Study rhythm</h2><div class="gap-kpi">{len(goals)}</div><p class="gap-muted">Active goals</p><div class="gap-kpi">{len(cards)}</div><p class="gap-muted">Flashcards due today</p><div class="gap-note">Progress is saved to your account. Flashcards appear here only when they are due and belong to you.</div></section></div><section class="gap-section"><h2>My goals</h2>{'<div class="gap-grid">'+goals_html+'</div>' if goals else '<div class="gap-empty">No goals yet. Create your first learning goal above.</div>'}</section><section class="gap-section"><h2>Review queue</h2>{'<div class="gap-grid">'+cards_html+'</div>' if cards else '<div class="gap-empty">You are all caught up. Add flashcards from Study Tools to build a review queue.</div>'}</section>'''
    return _page('Learning Planner',body)


@ui_gap_bp.route('/verified-reading', methods=['GET','POST'])
def verified_reading_page():
    u, db, _ = _ctx()
    if request.method=='POST':
        if not u: return redirect('/login')
        from verified_reading import record
        try: bid=int(request.form.get('book_id','0')); typ=request.form.get('event_type','session')
        except ValueError: abort(400)
        try:
            with db() as c:
                if not c.execute('SELECT 1 FROM books WHERE id=?',(bid,)).fetchone(): abort(404)
                accepted=record(c,u['id'],bid,typ)
        except ValueError as e: flash(str(e))
        else: flash('Reading event recorded.' if accepted else 'A similar event was already counted recently.')
        return redirect('/verified-reading')
    from verified_reading import leaderboard
    with db() as c:
        rankings=leaderboard(c,30,20)
        books=c.execute('SELECT id,title,author FROM books ORDER BY title').fetchall()
        names={r['id']:r['title'] for r in c.execute('SELECT id,title FROM books').fetchall()}
    items=''.join(f'<tr><td><span class="gap-pill">#{i}</span></td><td><b>{escape(names.get(r["book_id"],"Unknown title"))}</b></td><td>{r["unique_readers"]}</td><td>{r["sessions"]}</td><td>{r["completions"]}</td><td><b>{r["score"]:g}</b></td></tr>' for i,r in enumerate(rankings,1))
    opts=''.join(f'<option value="{b["id"]}">{escape(b["title"])} — {escape(b["author"] or "Unknown author")}</option>' for b in books)
    body=f'''<section class="gap-hero"><span class="gap-pill">🏆 Transparent reading metrics</span><h1>Verified reading & rankings</h1><p>Rankings use authenticated reading events and a documented scoring method. These signals reduce casual manipulation but are not a guarantee against coordinated abuse.</p></section><section class="gap-card"><h2>Record a reading milestone</h2>{'<form class="gap-form" method="post"><label>Book</label><select class="input" name="book_id" required>{opts}</select><label>Event type</label><select class="input" name="event_type"><option value="session">Reading session</option><option value="completion">Completed a book</option></select><button class="btn">Record milestone</button></form>' if u else '<p><a class="btn" href="/login">Sign in to record reading activity</a></p>'}</section><section class="gap-section"><div class="row between"><h2>Top books · last 30 days</h2><span class="gap-pill">Rolling 30-day window</span></div>{'<div class="gap-table-wrap"><table class="gap-table"><thead><tr><th>Rank</th><th>Book</th><th>Unique readers</th><th>Sessions</th><th>Completions</th><th>Score</th></tr></thead><tbody>'+items+'</tbody></table></div>' if rankings else '<div class="gap-empty">No qualified reading events yet. Rankings appear as authenticated readers use the reader.</div>'}<div class="gap-note" style="margin-top:12px"><b>Scoring methodology:</b> unique authenticated readers × 3, capped sessions × 0.3, unique completions × 5. Time window: rolling 30 days.</div></section>'''
    return _page('Verified Reading',body)


@ui_gap_bp.route('/refunds', methods=['GET','POST'])
def customer_refunds_page():
    u, db, _ = _ctx()
    if not u: return redirect('/login')
    if request.method=='POST':
        from refund_engine import request_refund, RefundError
        try:
            order_id=int(request.form.get('order_id','0'))
            amount=Decimal(request.form.get('amount','0'))
            if not amount.is_finite() or amount<=0 or amount.as_tuple().exponent < -2: raise ValueError()
            cents=int(amount*100)
        except (ValueError,InvalidOperation): abort(400,'Enter a valid refund amount.')
        reason=request.form.get('reason','').strip()
        try:
            with db() as c: rid=request_refund(c,order_id,u['id'],cents,reason)
        except RefundError as e: flash(str(e))
        else: flash(f'Refund request #{rid} submitted for review. No money has been refunded.')
        return redirect('/refunds')
    with db() as c:
        orders=c.execute('''SELECT o.id,o.total,o.status,o.created,pa.state AS payment_state
          FROM orders o JOIN payment_attempts pa ON pa.order_id=o.id AND pa.state='paid'
          WHERE o.user_id=? ORDER BY o.id DESC''',(u['id'],)).fetchall()
        refunds=c.execute('''SELECT r.id,r.order_id,r.amount_cents,r.reason,r.state,r.created FROM refund_requests r JOIN orders o ON o.id=r.order_id WHERE o.user_id=? ORDER BY r.id DESC''',(u['id'],)).fetchall()
    opts=''.join(f'<option value="{o["id"]}">Order #{o["id"]} · ৳{o["total"]:.2f} · {escape(o["created"][:10] if o["created"] else "")}</option>' for o in orders)
    items=''.join(f'<tr><td>#{r["id"]}</td><td>#{r["order_id"]}</td><td>৳{r["amount_cents"]/100:.2f}</td><td>{escape(r["reason"])}</td><td>{_status(r["state"])}</td><td>{escape((r["created"] or "")[:10])}</td></tr>' for r in refunds)
    body=f'''<section class="gap-hero"><span class="gap-pill">🛡 Order support</span><h1>Refund requests</h1><p>Submit a request for a verified paid order and track its review status. Approval is not the same as a completed gateway refund.</p></section><div class="gap-grid"><section class="gap-card"><h2>Start a request</h2>{'<form class="gap-form" method="post"><label>Paid order</label><select class="input" name="order_id" required>{opts}</select><label>Requested amount (BDT)</label><input class="input" type="number" name="amount" min="0.01" step="0.01" required placeholder="e.g. 250.00"><label>Reason</label><textarea class="input" name="reason" minlength="5" maxlength="500" rows="4" required placeholder="Explain why you are requesting a refund"></textarea><button class="btn">Submit request</button></form>' if orders else '<div class="gap-empty">No verified paid orders are eligible to start a refund request right now.</div>'}</section><section class="gap-card"><h2>Before you submit</h2><p class="gap-muted">Requests are checked against the paid transaction and remaining refundable balance.</p><div class="gap-note">This interface records and tracks a request only. It does not initiate a real payment-provider refund. Do not submit duplicate requests for the same amount.</div><p><a href="/my/orders">View my orders →</a></p></section></div><section class="gap-section"><h2>Request history</h2>{'<div class="gap-table-wrap"><table class="gap-table"><thead><tr><th>Request</th><th>Order</th><th>Amount</th><th>Reason</th><th>Status</th><th>Submitted</th></tr></thead><tbody>'+items+'</tbody></table></div>' if refunds else '<div class="gap-empty">Your refund requests will appear here.</div>'}</section>'''
    return _page('Refund Requests',body)


@ui_gap_bp.route('/admin/refunds', methods=['GET','POST'])
def admin_refunds_page():
    u=_require({'admin'})
    from app import db
    from refund_engine import review_refund, RefundError
    if request.method=='POST':
        try: rid=int(request.form.get('refund_id','0')); approve=request.form.get('decision')=='approve'
        except ValueError: abort(400)
        try:
            with db() as c: review_refund(c,rid,u['id'],approve,admin=True)
        except RefundError as e: flash(str(e))
        else: flash('Request approved for manual gateway handling.' if approve else 'Request rejected.')
        return redirect('/admin/refunds')
    with db() as c:
        rows=c.execute('''SELECT r.id,r.order_id,r.amount_cents,r.reason,r.state,r.created,o.user_id,u.name AS customer
          FROM refund_requests r JOIN orders o ON o.id=r.order_id JOIN users u ON u.id=o.user_id ORDER BY CASE r.state WHEN 'requested' THEN 0 ELSE 1 END,r.id DESC LIMIT 200''').fetchall()
        counts={r['state']:r['n'] for r in c.execute('SELECT state,COUNT(*) n FROM refund_requests GROUP BY state').fetchall()}
    items=''.join(f'''<tr><td><b>#{r['id']}</b><div class="gap-muted gap-small">Order #{r['order_id']}</div></td><td>{escape(r['customer'] or 'Customer')}</td><td>৳{r['amount_cents']/100:.2f}</td><td>{escape(r['reason'])}</td><td>{_status(r['state'])}</td><td>{escape((r['created'] or '')[:10])}</td><td>{'<form method="post" class="gap-actions"><input type="hidden" name="refund_id" value="'+str(r['id'])+'"><button class="btn green" name="decision" value="approve">Approve</button><button class="btn ghost gap-btn-danger" name="decision" value="reject">Reject</button></form>' if r['state']=='requested' else '—'}</td></tr>''' for r in rows)
    body=f'''<section class="gap-hero"><span class="gap-pill">🔐 Admin only</span><h1>Refund review queue</h1><p>Review customer requests, check the recorded order/payment state and approve or reject the request. This queue does not move money.</p></section><div class="gap-statrow">{''.join(f'<div class="gap-stat"><div class="gap-muted gap-small">{escape(k.title())}</div><div class="gap-kpi">{v}</div></div>' for k,v in sorted(counts.items())) or '<div class="gap-stat"><div class="gap-muted">No requests yet</div><div class="gap-kpi">0</div></div>'}</div><div class="gap-note">An approved request is still awaiting manual/provider-side refund processing. The UI never labels an approval as “refunded”.</div><section class="gap-section"><h2>All requests</h2>{'<div class="gap-table-wrap"><table class="gap-table"><thead><tr><th>Request</th><th>Customer</th><th>Amount</th><th>Reason</th><th>Status</th><th>Created</th><th>Review action</th></tr></thead><tbody>'+items+'</tbody></table></div>' if rows else '<div class="gap-empty">No refund requests in the queue.</div>'}</section>'''
    return _page('Refund Review Queue',body)


@ui_gap_bp.get('/creator/royalties')
def creator_royalties_page():
    u=_require({'creator','admin'})
    from app import db
    from royalty_engine import creator_report
    from royalty_payouts import balance as payout_balance, list_requests
    with db() as c:
        items=creator_report(c,u['id'])
        bal=payout_balance(c,u['id'])
        payouts=list_requests(c,u['id'])
        books={r['id']:r['title'] for r in c.execute('SELECT id,title FROM books').fetchall()}
    rows=''.join(f'<tr><td><b>{escape(books.get(x["book_id"],"Book #"+str(x["book_id"])))}</b></td><td>{x["items"]}</td><td>৳{x["gross_cents"]/100:.2f}</td><td><b>৳{x["royalty_cents"]/100:.2f}</b></td></tr>' for x in items)
    total=sum(x['royalty_cents'] for x in items)/100
    body=f'''<section class="gap-hero"><span class="gap-pill">✦ Creator finance</span><h1>Royalty ledger</h1><p>Review recorded royalties by title. These are accounting records only; payouts are handled through an admin-reviewed manual reconciliation workflow.</p></section><div class="gap-statrow"><div class="gap-stat"><div class="gap-muted gap-small">Titles with royalties</div><div class="gap-kpi">{len(items)}</div></div><div class="gap-stat"><div class="gap-muted gap-small">Recorded royalty total</div><div class="gap-kpi">৳{total:,.2f}</div></div><div class="gap-stat"><div class="gap-muted gap-small">Payout status</div><div style="margin-top:8px">{_status('Manual review only')}</div></div></div><div class="gap-note">Requests reserve the available balance and require admin review. No money is transferred automatically.</div><section class="gap-section"><h2>Royalty by title</h2>{'<div class="gap-table-wrap"><table class="gap-table"><thead><tr><th>Title</th><th>Items</th><th>Gross sales</th><th>Recorded royalty</th></tr></thead><tbody>'+rows+'</tbody></table></div>' if items else '<div class="gap-empty">No royalty ledger entries are recorded for your account yet.</div>'}</section>'''
    token=secrets.token_urlsafe(24)
    payout_rows=''.join(f'<tr><td>#{p["id"]}</td><td>৳{p["amount_cents"]/100:.2f}</td><td>{escape(p["method"].replace("_"," ").title())} · {escape(p["destination_masked"])}</td><td>{_status(p["status"])}</td><td>{escape((p["created_at"] or "")[:16])}</td></tr>' for p in payouts)
    payout_section=f'''<div class="gap-statrow"><div class="gap-stat"><div class="gap-muted gap-small">Available to request</div><div class="gap-kpi">৳{bal['available_cents']/100:,.2f}</div></div><div class="gap-stat"><div class="gap-muted gap-small">Reserved / pending</div><div class="gap-kpi">৳{bal['reserved_cents']/100:,.2f}</div></div><div class="gap-stat"><div class="gap-muted gap-small">Recorded paid</div><div class="gap-kpi">৳{bal['paid_cents']/100:,.2f}</div></div></div><section class="gap-card"><h2>Request a payout</h2><p class="gap-muted">Requests require admin review. Destination details are encrypted at rest using SECRET_KEY.</p><form class="gap-form" method="post" action="/creator/royalties/request"><input type="hidden" name="idempotency_key" value="{token}"><label>Amount (BDT)</label><input class="input" type="number" name="amount" min="1" max="{bal['available_cents']/100:.2f}" step="0.01" required><label>Payment method</label><select class="input" name="method" required><option value="bkash">bKash</option><option value="nagad">Nagad</option><option value="bank_transfer">Bank transfer</option></select><label>Destination details</label><input class="input" name="destination" minlength="5" maxlength="180" autocomplete="off" required><button class="btn" {'disabled' if bal['available_cents']<100 else ''}>Submit payout request</button></form></section><section class="gap-section"><h2>Payout history</h2>{('<div class="gap-table-wrap"><table class="gap-table"><thead><tr><th>Request</th><th>Amount</th><th>Destination</th><th>Status</th><th>Created</th></tr></thead><tbody>'+payout_rows+'</tbody></table></div>') if payouts else '<div class="gap-empty">No payout requests yet.</div>'}</section>'''
    body += payout_section
    return _page('Creator Royalties',body)


@ui_gap_bp.post('/creator/royalties/request')
def creator_royalty_payout_request_form():
    u=_require({'creator','admin'})
    from app import db
    from royalty_payouts import request_payout
    try:
        amount=Decimal(request.form.get('amount','0'))
        if not amount.is_finite() or amount<=0 or amount.as_tuple().exponent < -2: raise ValueError('Enter a valid payout amount with up to two decimal places.')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            request_payout(c,u['id'],int(amount*100),request.form.get('method',''),request.form.get('destination',''),request.form.get('idempotency_key',''))
            c.commit()
    except (ValueError,RuntimeError) as e: flash(str(e))
    else: flash('Payout request submitted for admin review. No money has been transferred.')
    return redirect('/creator/royalties')


@ui_gap_bp.route('/admin/royalty-payouts', methods=['GET','POST'])
def admin_royalty_payouts_page():
    u=_require({'admin'})
    from app import db
    from royalty_payouts import list_requests, transition, decrypt_destination
    if request.method=='POST':
        try:
            payout_id=int(request.form.get('payout_id','0'))
            with db() as c:
                transition(c,payout_id,u['id'],request.form.get('status',''),request.form.get('note',''),request.form.get('provider_reference',''))
                c.commit()
        except (ValueError,LookupError) as e: flash(str(e))
        else: flash('Payout status updated. This did not initiate a bank/mobile-wallet transfer.')
        return redirect('/admin/royalty-payouts')
    with db() as c: payouts=list_requests(c,limit=300)
    rows=[]
    for p in payouts:
        destination=''
        if p['status'] in ('approved','processing'):
            try: destination=decrypt_destination(p['destination_ciphertext'])
            except Exception: destination='[Cannot decrypt: check SECRET_KEY]'
        if p['status']=='requested': opts='<option value="approved">Approve</option><option value="rejected">Reject</option>'
        elif p['status']=='approved': opts='<option value="processing">Mark processing</option><option value="paid">Mark paid (verified transfer)</option><option value="failed">Mark failed</option><option value="rejected">Reject</option>'
        elif p['status']=='processing': opts='<option value="paid">Mark paid (verified transfer)</option><option value="failed">Mark failed</option>'
        elif p['status']=='failed': opts='<option value="processing">Retry processing</option>'
        else: opts=''
        actions='—'
        if opts:
            actions=f'<form class="gap-form" method="post"><input type="hidden" name="payout_id" value="{p["id"]}"><select class="input" name="status">{opts}</select><input class="input" name="provider_reference" placeholder="Required for Paid; real transaction ref"><input class="input" name="note" maxlength="500" placeholder="Review note / reason"><button class="btn">Save status</button></form>'
        provider_actions=''
        if p['status'] in ('approved','failed'):
            provider_actions=f'<button type="button" class="btn green" data-payout-submit="{p["id"]}">Submit transfer</button>'
        if p['status'] in ('processing','failed'):
            provider_actions+=f'<button type="button" class="btn ghost" data-payout-reconcile="{p["id"]}">Reconcile status</button>'
        reveal=f'<details><summary>Reveal destination</summary><code>{escape(destination)}</code></details>' if destination else ''
        rows.append(f'<tr><td>#{p["id"]}<div class="gap-muted gap-small">{escape(p.get("creator_name") or "Creator")} · {escape(p.get("creator_email") or "")}</div></td><td><b>৳{p["amount_cents"]/100:.2f}</b></td><td>{escape(p["method"].replace("_"," ").title())}<div class="gap-muted gap-small">{escape(p["destination_masked"])}</div>{reveal}</td><td>{_status(p["status"])}</td><td>{escape(p.get("provider_reference") or "—")}</td><td>{actions}<div class="gap-actions">{provider_actions}</div></td></tr>')
    table='<div class="gap-table-wrap"><table class="gap-table"><thead><tr><th>Creator</th><th>Amount</th><th>Destination</th><th>Status</th><th>Transfer reference</th><th>Review action</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>' if rows else '<div class="gap-empty">No payout requests have been submitted.</div>'
    body='<section class="gap-hero"><span class="gap-pill">Admin finance</span><h1>Creator payout review</h1><p>Approve/reject requests and reconcile real provider transfers. Paid status must be backed by a unique verified transaction reference.</p></section><div class="gap-note">Submit transfer is available only after approval and a configured merchant-approved gateway. Ambiguous outcomes must be reconciled before retrying. Manual status changes remain available for audited finance operations.</div><p id="payout-provider-message" role="status" aria-live="polite"></p><section class="gap-section"><h2>Requests</h2>'+table+'</section><script src="/static/admin-royalty-payouts.js" defer></script>'
    return _page('Creator Payout Review',body)


@ui_gap_bp.route('/admin/royalty-contracts', methods=['GET','POST'])
def admin_royalty_contracts_page():
    u=_require({'admin'})
    from app import db
    if request.method=='POST':
        try:
            book_id=int(request.form.get('book_id','0')); creator_id=int(request.form.get('creator_user_id','0')); percent=Decimal(request.form.get('royalty_percent','-1'))
            if not percent.is_finite() or percent<0 or percent>100 or percent.as_tuple().exponent < -2: raise ValueError()
            bps=int(percent*100)
        except (ValueError,InvalidOperation): abort(400,'Enter a valid book, creator and royalty percentage.')
        with db() as c:
            if not c.execute('SELECT 1 FROM books WHERE id=?',(book_id,)).fetchone(): abort(404,'Book not found')
            if not c.execute("SELECT 1 FROM users WHERE id=? AND role='creator'",(creator_id,)).fetchone(): abort(404,'Creator account not found')
            c.execute('''INSERT INTO royalty_contracts(book_id,creator_user_id,royalty_bps) VALUES(?,?,?)
              ON CONFLICT(book_id) DO UPDATE SET creator_user_id=excluded.creator_user_id,royalty_bps=excluded.royalty_bps,active=1''',(book_id,creator_id,bps))
            c.commit()
        flash('Royalty contract saved. This does not enable payouts.')
        return redirect('/admin/royalty-contracts')
    with db() as c:
        books=c.execute('SELECT id,title FROM books ORDER BY title').fetchall()
        creators=c.execute("SELECT id,name,email FROM users WHERE role='creator' ORDER BY name").fetchall()
        rows=c.execute('''SELECT rc.book_id,rc.creator_user_id,rc.royalty_bps,rc.active,b.title,u.name FROM royalty_contracts rc JOIN books b ON b.id=rc.book_id JOIN users u ON u.id=rc.creator_user_id ORDER BY b.title''').fetchall()
    book_opts=''.join(f'<option value="{b["id"]}">{escape(b["title"])}</option>' for b in books)
    creator_opts=''.join(f'<option value="{x["id"]}">{escape(x["name"] or x["email"])} — #{x["id"]}</option>' for x in creators)
    items=''.join(f'<tr><td><b>{escape(r["title"])}</b></td><td>{escape(r["name"] or "Creator")}</td><td>{r["royalty_bps"]/100:.2f}%</td><td>{_status("Active" if r["active"] else "Inactive")}</td></tr>' for r in rows)
    body=f'''<section class="gap-hero"><span class="gap-pill">⚙ Admin finance</span><h1>Royalty contracts</h1><p>Assign a creator and royalty rate to a book. Contracts feed the accounting ledger; they do not transfer funds or verify legal ownership by themselves.</p></section><div class="gap-grid"><section class="gap-card"><h2>Create or update contract</h2><form class="gap-form" method="post"><label>Book</label><select class="input" name="book_id" required><option value="">Choose book…</option>{book_opts}</select><label>Creator account</label><select class="input" name="creator_user_id" required><option value="">Choose creator…</option>{creator_opts}</select><label>Royalty rate (%)</label><input class="input" type="number" name="royalty_percent" min="0" max="100" step="0.01" placeholder="e.g. 12.50" required><button class="btn">Save contract</button></form></section><section class="gap-card"><h2>Contract controls</h2><p class="gap-muted">Rates are stored as basis points for precise integer-cent calculations. One active contract is maintained per book in the current engine.</p><div class="gap-note">Before production use, confirm publisher/creator rights, signed contract references, tax handling and payout verification outside this prototype.</div></section></div><section class="gap-section"><h2>Existing contracts</h2>{'<div class="gap-table-wrap"><table class="gap-table"><thead><tr><th>Book</th><th>Creator</th><th>Royalty rate</th><th>Status</th></tr></thead><tbody>'+items+'</tbody></table></div>' if rows else '<div class="gap-empty">No royalty contracts configured yet.</div>'}</section>'''
    return _page('Royalty Contracts',body)
