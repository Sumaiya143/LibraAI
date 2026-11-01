"""Account data portability: authenticated, scoped exports with no password hashes."""
import json
import sqlite3
from datetime import datetime, timezone
from flask import Blueprint, abort, current_app, jsonify, redirect, render_template_string, request, session, url_for

account_bp = Blueprint('account_privacy', __name__)
from account_export_core import export_account_data
from account_security_core import change_password, PasswordChangeError
from hashlib import sha256
from werkzeug.security import check_password_hash, generate_password_hash
from flask import flash


def _valid_credential_session(uid):
    """Reject stale or legacy sessions for account-security endpoints."""
    conn = sqlite3.connect(current_app.config['LIBRAAI_ACCOUNT_DB'])
    try:
        row = conn.execute('SELECT password FROM users WHERE id=?', (int(uid),)).fetchone()
    finally:
        conn.close()
    fingerprint = session.get('_credential_fingerprint')
    valid = bool(row and fingerprint and fingerprint == sha256(str(row[0]).encode('utf-8')).hexdigest())
    if not valid:
        session.clear()
    return valid

@account_bp.get('/account/export')
def account_export():
    uid = session.get('uid')
    if not uid or not _valid_credential_session(uid):
        return redirect(url_for('login'))
    conn = sqlite3.connect(current_app.config['LIBRAAI_ACCOUNT_DB'])
    try:
        data = export_account_data(conn, uid)
    except LookupError:
        abort(404)
    finally:
        conn.close()
    response = jsonify(data)
    response.headers['Content-Disposition'] = 'attachment; filename="libraai-account-data.json"'
    response.headers['Cache-Control'] = 'no-store'
    return response


@account_bp.get('/account')
def account_page():
    if not session.get('uid') or not _valid_credential_session(session['uid']):
        return redirect(url_for('login'))
    return render_template_string('''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>My account · LibraAI</title><style>body{font-family:system-ui;background:#f6f7ff;color:#18213d;margin:0}.wrap{max-width:720px;margin:8vh auto;padding:24px}.card{background:white;padding:32px;border-radius:22px;box-shadow:0 20px 70px #29316a15}a{color:#5948c8}a.button{display:inline-block;background:#5948c8;color:white;padding:13px 18px;border-radius:12px;text-decoration:none}p{line-height:1.7}</style></head><body><main class="wrap"><div class="card"><p><a href="/">← Dashboard</a></p><h1>My account &amp; privacy</h1><p>Download a JSON copy of your account profile and your reading, study and activity records. Password hashes are excluded. The export is available only while signed in to your account.</p><p><a class="button" href="/account/export">Download my data</a></p><p><strong>Account security</strong></p><form method="post" action="/account/password" autocomplete="off"><label for="current">Current password</label><input id="current" type="password" name="current_password" autocomplete="current-password" required><label for="new">New password (12–128 characters)</label><input id="new" type="password" name="new_password" autocomplete="new-password" minlength="12" maxlength="128" required><input type="hidden" name="_csrf" value="{{csrf_token}}"><button type="submit">Change password</button></form><p>{% for message in get_flashed_messages() %}{{message}}{% endfor %}</p><p>For account deletion or privacy requests, contact the site operator. Do not include your password in any message.</p></div></main></body></html>''', csrf_token=session.setdefault('_csrf', __import__('secrets').token_urlsafe(32)))


@account_bp.post('/account/password')
def change_account_password():
    uid = session.get('uid')
    if not uid or not _valid_credential_session(uid):
        return redirect(url_for('login'))
    conn = sqlite3.connect(current_app.config['LIBRAAI_ACCOUNT_DB'])
    changed = False
    try:
        change_password(conn, int(uid), request.form.get('current_password', ''),
                        request.form.get('new_password', ''), check_password_hash, generate_password_hash)
        changed = True
    except PasswordChangeError as exc:
        flash(str(exc))
    finally:
        conn.close()
    if changed:
        # Rotate the per-session CSRF secret after a credential change so any
        # previously rendered forms in this browser cannot be replayed.
        import secrets
        # Keep this browser signed in, but invalidate sessions on other devices:
        # their credential fingerprint still refers to the previous password hash.
        verify_conn = sqlite3.connect(current_app.config['LIBRAAI_ACCOUNT_DB'])
        try:
            row = verify_conn.execute('SELECT password FROM users WHERE id=?', (int(uid),)).fetchone()
            if row is None:
                session.clear()
                return redirect(url_for('login'))
            session['_credential_fingerprint'] = sha256(str(row[0]).encode('utf-8')).hexdigest()
        finally:
            verify_conn.close()
        session['_csrf'] = secrets.token_urlsafe(32)
        flash('Password updated successfully. Other signed-in devices must sign in again.')
    return redirect(url_for('account_privacy.account_page'))
