"""Authenticated waitlist web/API endpoints; uses application's global CSRF filter."""
from flask import Blueprint, request, session, jsonify, abort
from waitlist_engine import setup, join, cancel, offer_next, accept, WaitlistError

waitlist_bp=Blueprint('waitlist',__name__)

def conn():
    from app import db
    return db()

def user():
    from app import current_user
    u=current_user()
    if u is None: abort(401)
    return u

@waitlist_bp.get('/api/waitlist')
def list_entries():
    u=user()
    with conn() as c:
        entries=c.execute('SELECT w.id,w.book_id,b.title,w.status,w.joined_at,w.expires_at FROM book_waitlist w JOIN books b ON b.id=w.book_id WHERE w.user_id=? ORDER BY w.id DESC',(u['id'],)).fetchall()
    return jsonify([dict(r) for r in entries])

@waitlist_bp.post('/api/waitlist/join')
def join_entry():
    u=user(); data=request.get_json(silent=True) or {}
    try:
        book_id=int(data.get('book_id',0))
        with conn() as c: entry_id=join(c,u['id'],book_id)
    except (ValueError,TypeError,WaitlistError) as e: return jsonify(error=str(e)),400
    return jsonify(id=entry_id,status='waiting'),201

@waitlist_bp.post('/api/waitlist/<int:entry_id>/cancel')
def cancel_entry(entry_id):
    u=user()
    try:
        with conn() as c: cancel(c,u['id'],entry_id)
    except WaitlistError as e: return jsonify(error=str(e)),400
    return jsonify(status='cancelled')

@waitlist_bp.post('/api/waitlist/<int:entry_id>/accept')
def accept_entry(entry_id):
    u=user()
    try:
        with conn() as c: book_id=accept(c,u['id'],entry_id)
    except WaitlistError as e: return jsonify(error=str(e)),400
    return jsonify(status='accepted',book_id=book_id,notice='Offer accepted; library staff must confirm collection or loan')

@waitlist_bp.post('/api/admin/waitlist/<int:book_id>/offer')
def admin_offer(book_id):
    u=user()
    if u['role']!='admin': abort(403)
    try:
        with conn() as c: entry_id=offer_next(c,book_id)
    except WaitlistError as e: return jsonify(error=str(e)),400
    return jsonify(id=entry_id,status='offered' if entry_id else 'empty')
