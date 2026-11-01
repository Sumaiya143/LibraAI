"""Customer support portal; shares the host application's authentication and CSRF."""
from flask import Blueprint, abort, flash, redirect, render_template_string, request, url_for
from support_engine import CATEGORIES, STATUSES, setup, create_ticket, get_ticket, add_message, change_status

support_bp = Blueprint('support', __name__)

def install(app, db, current_user):
    with db() as conn:
        setup(conn)

    def identity():
        user = current_user()
        if user is None: abort(401)
        return user

    def render(body, **data):
        from flask import session
        import secrets
        token = session.setdefault('_csrf', secrets.token_urlsafe(32))
        return render_template_string("""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LibraAI Support</title><style>body{font-family:system-ui;background:#f6f7fc;color:#17213c;margin:0}header{background:#171c44;color:white;padding:22px max(20px,calc((100vw - 900px)/2))}main{max-width:900px;margin:35px auto;padding:0 20px}.card{background:white;padding:24px;border-radius:18px;margin:16px 0;box-shadow:0 7px 28px #151d3510}input,textarea,select{display:block;width:100%;box-sizing:border-box;margin:9px 0 17px;padding:12px;border:1px solid #cbd2e2;border-radius:9px;font:inherit}button,.button{display:inline-block;background:#5146ca;color:white;border:0;border-radius:9px;padding:11px 17px;text-decoration:none;cursor:pointer}a{color:#4339a9}small{color:#5e6780}.message{border-left:3px solid #6a5fe2;padding:10px 15px;background:#f6f5ff;margin:12px 0;white-space:pre-wrap}label{font-weight:600}</style></head><body><header><strong>LibraAI</strong> · Help & Support</header><main><p><a href="/">← Dashboard</a> · <a href="/support">Support tickets</a></p>""" + body + """</main></body></html>""", csrf=token, **data)

    @support_bp.route('/support', methods=['GET'])
    def index():
        user = identity(); admin = user['role'] == 'admin'
        with db() as conn:
            if admin:
                rows = conn.execute('SELECT t.*,u.email FROM support_tickets t JOIN users u ON u.id=t.user_id ORDER BY t.updated_at DESC LIMIT 100').fetchall()
            else:
                rows = conn.execute('SELECT * FROM support_tickets WHERE user_id=? ORDER BY updated_at DESC LIMIT 100',(user['id'],)).fetchall()
        return render("""<h1>Support center</h1><p>Need help with reading, orders, or your library? Create a ticket and track replies.</p><a class="button" href="/support/new">Create ticket</a><section class="card"><h2>Tickets</h2>{% if not rows %}<p>No support tickets yet.</p>{% endif %}{% for t in rows %}<p><a href="{{url_for('support.detail',ticket_id=t['id'])}}">#{{t['id']}} · {{t['subject']}}</a> <small>({{t['status']}}{% if admin %} · {{t['email']}}{% endif %})</small></p>{% endfor %}</section>""",rows=rows,admin=admin)

    @support_bp.route('/support/new',methods=['GET','POST'])
    def new():
        user=identity()
        if request.method=='POST':
            with db() as conn:
                try: ticket_id=create_ticket(conn,user['id'],request.form.get('subject'),request.form.get('category'),request.form.get('message'))
                except ValueError as exc: abort(400,str(exc))
            return redirect(url_for('support.detail',ticket_id=ticket_id))
        return render("""<section class="card"><h1>Create support ticket</h1><form method="post"><input type="hidden" name="_csrf" value="{{csrf}}"><label for="subject">Subject</label><input id="subject" name="subject" maxlength="140" minlength="5" required><label for="category">Category</label><select id="category" name="category">{% for category in categories %}<option value="{{category}}">{{category|title}}</option>{% endfor %}</select><label for="message">Describe the issue</label><textarea id="message" name="message" minlength="10" maxlength="5000" rows="7" required></textarea><button>Submit ticket</button></form></section>""",categories=sorted(CATEGORIES))

    @support_bp.route('/support/<int:ticket_id>',methods=['GET'])
    def detail(ticket_id):
        user=identity(); admin=user['role']=='admin'
        with db() as conn:
            ticket=get_ticket(conn,ticket_id,user['id'],admin)
            if ticket is None: abort(404)
            messages=conn.execute('SELECT m.*,u.name FROM support_messages m JOIN users u ON u.id=m.author_id WHERE m.ticket_id=? ORDER BY m.id',(ticket_id,)).fetchall()
        return render("""<section class="card"><h1>Ticket #{{ticket['id']}} · {{ticket['subject']}}</h1><p><small>{{ticket['category']}} · {{ticket['status']}}</small></p>{% for m in messages %}<div class="message"><strong>{{m['name']}}</strong> · <small>{{m['created_at']}}</small><p>{{m['body']}}</p></div>{% endfor %}{% if ticket['status'] != 'closed' %}<form method="post" action="{{url_for('support.reply',ticket_id=ticket['id'])}}"><input type="hidden" name="_csrf" value="{{csrf}}"><label for="body">Reply</label><textarea id="body" name="message" rows="4" maxlength="5000" required></textarea><button>Send reply</button></form>{% endif %}{% if admin %}<form method="post" action="{{url_for('support.status',ticket_id=ticket['id'])}}"><input type="hidden" name="_csrf" value="{{csrf}}"><label for="status">Update status</label><select id="status" name="status">{% for s in statuses %}<option value="{{s}}" {% if s == ticket['status'] %}selected{% endif %}>{{s}}</option>{% endfor %}</select><button>Update status</button></form>{% endif %}</section>""",ticket=ticket,messages=messages,admin=admin,statuses=sorted(STATUSES))

    @support_bp.route('/support/<int:ticket_id>/reply',methods=['POST'])
    def reply(ticket_id):
        user=identity()
        with db() as conn:
            try: add_message(conn,ticket_id,user['id'],request.form.get('message'),user['role']=='admin')
            except PermissionError: abort(404)
            except ValueError as exc: abort(400,str(exc))
        return redirect(url_for('support.detail',ticket_id=ticket_id))

    @support_bp.route('/support/<int:ticket_id>/status',methods=['POST'])
    def status(ticket_id):
        user=identity()
        with db() as conn:
            try: change_status(conn,ticket_id,request.form.get('status'),user['role']=='admin')
            except PermissionError: abort(403)
            except ValueError as exc: abort(400,str(exc))
            except LookupError: abort(404)
        return redirect(url_for('support.detail',ticket_id=ticket_id))

    app.register_blueprint(support_bp)
