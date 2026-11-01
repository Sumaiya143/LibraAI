"""Rights-aware private audiobook hosting and streaming for LibraAI.

Uploads are private objects (never static files). The uploader must attest to
rights; metadata alone is not legal clearance. Production cloud storage requires
configured S3/MinIO credentials and a persistent database.
"""
from __future__ import annotations
import hashlib, io, os, re, uuid
from datetime import datetime, timezone
from flask import Blueprint, abort, current_app, jsonify, request, session

bp = Blueprint('audiobook_library', __name__)
AUDIO_TYPES = {
    '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4', '.aac': 'audio/aac',
    '.ogg': 'audio/ogg', '.oga': 'audio/ogg', '.opus': 'audio/ogg',
    '.wav': 'audio/wav', '.flac': 'audio/flac', '.webm': 'audio/webm',
}
MAX_AUDIO_BYTES = max(1, min(200, int(os.getenv('LIBRAAI_MAX_AUDIO_UPLOAD_MB', '200')))) * 1024 * 1024

@bp.before_request
def set_audio_upload_limit():
    # Apply the larger body limit only to the protected audio upload endpoint.
    if request.endpoint == 'audiobook_library.upload_audiobook_asset':
        request.max_content_length = MAX_AUDIO_BYTES + 2 * 1024 * 1024


def setup(connect):
    with connect() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS audiobook_assets (
            id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL UNIQUE REFERENCES books(id) ON DELETE CASCADE,
            storage_key TEXT NOT NULL UNIQUE, original_name TEXT NOT NULL, mime_type TEXT NOT NULL,
            file_size INTEGER NOT NULL, sha256_hex TEXT NOT NULL,
            rights_holder TEXT NOT NULL, license_reference TEXT NOT NULL,
            license_status TEXT NOT NULL DEFAULT 'active' CHECK(license_status IN ('active','expired','revoked')),
            license_expires_at TEXT, access_policy TEXT NOT NULL DEFAULT 'licensed' CHECK(access_policy IN ('sample','licensed')),
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_audiobook_assets_status ON audiobook_assets(active,license_status,book_id)')


def _admin_user():
    from app import current_user
    user = current_user()
    if not user:
        abort(401)
    if user['role'] != 'admin':
        abort(403)
    return user


def _now():
    return datetime.now(timezone.utc)


def _license_valid(row):
    if not row or row['active'] != 1 or row['license_status'] != 'active':
        return False
    expiry = row['license_expires_at']
    if expiry:
        try:
            parsed = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if parsed <= _now():
                return False
        except ValueError:
            return False
    return True




@bp.get('/admin/audiobook-library')
def admin_audiobook_library():
    _admin_user()
    from app import db, page
    with db() as c:
        books = c.execute("SELECT id,title,author FROM books ORDER BY title LIMIT 1000").fetchall()
        assets = c.execute("SELECT a.*,b.title AS book_title FROM audiobook_assets a JOIN books b ON b.id=a.book_id ORDER BY a.updated_at DESC LIMIT 200").fetchall()
    html = r'''
    <style>
    .audio-hero{padding:28px;border-radius:22px;color:#fff;background:radial-gradient(circle at 85% 10%,#a5f3fc55,transparent 25%),linear-gradient(120deg,#171b61,#4338ca 60%,#8b5cf6);margin-bottom:18px}
    .audio-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.audio-card{background:var(--card,#fff);border:1px solid #dfe3ff;border-radius:18px;padding:20px;box-shadow:0 12px 32px #302e8010}.audio-card label{display:block;font-weight:700;margin:12px 0 6px}.audio-card input,.audio-card select{width:100%;box-sizing:border-box}.audio-note{background:#f1f5ff;border:1px solid #dce5ff;padding:12px;border-radius:12px;color:#3c4a73;font-size:13px;line-height:1.5}.audio-status{margin-top:12px;padding:12px;border-radius:12px;white-space:pre-wrap}.audio-status.ok{background:#ecfdf5;color:#065f46}.audio-status.err{background:#fff1f2;color:#9f1239}
    </style>
    <section class="audio-hero"><span class="pill">Private media · rights-aware</span><h1>Audiobook Hosting & Licensing</h1><p>Upload audio privately, record the rights holder and license reference, and control playback through entitlement checks.</p></section>
    <div class="audio-grid"><section class="audio-card"><h2>Register audiobook asset</h2><div class="audio-note">Only upload files you have permission to host and stream. A rights reference is recorded for auditability; it does not independently verify legal rights. Use <b>Public sample</b> only for a short preview file you are authorized to share publicly.</div>
    <form id="audioUploadForm" enctype="multipart/form-data"><label for="book_id">Catalog book</label><select class="input" id="book_id" name="book_id" required><option value="">Choose a title</option>{% for b in books %}<option value="{{ b['id'] }}">#{{ b['id'] }} — {{ b['title'] }} · {{ b['author'] }}</option>{% endfor %}</select>
    <label for="audio">Audio file (MP3, M4A, AAC, OGG, OPUS, WAV, FLAC, WEBM)</label><input class="input" id="audio" name="audio" type="file" accept=".mp3,.m4a,.aac,.ogg,.oga,.opus,.wav,.flac,.webm,audio/*" required>
    <label for="rights_holder">Rights holder</label><input class="input" id="rights_holder" name="rights_holder" maxlength="200" required placeholder="Publisher / author / distributor">
    <label for="license_reference">License / agreement reference</label><input class="input" id="license_reference" name="license_reference" maxlength="200" required placeholder="Agreement ID or internal reference">
    <label for="license_expires_at">License expiry (optional ISO date/time)</label><input class="input" id="license_expires_at" name="license_expires_at" placeholder="2027-12-31T23:59:59+00:00">
    <label for="access_policy">Access policy</label><select class="input" id="access_policy" name="access_policy"><option value="licensed">Paid entitlement required</option><option value="sample">Public short sample</option></select>
    <button class="btn" id="audioSubmit" type="submit">Upload & register securely</button><div id="audioResult" role="status" aria-live="polite"></div></form></section>
    <section class="audio-card"><h2>Hosting readiness</h2><p>Assets are stored outside the public static directory. Playback supports HTTP byte ranges for seeking and verifies the SHA-256 digest before serving.</p><ul><li>Private local storage for development</li><li>S3 / MinIO option when credentials are configured</li><li>License expiry, revocation and active-state controls</li><li>Authenticated playback with digital entitlement</li><li>Bounded upload size; configurable up to 200 MB</li></ul><div class="audio-note">Production hosting still needs persistent private object storage, backup/retention policy, publisher agreements, consent/rights verification, monitoring and load testing.</div></section></div>
    <section class="audio-card" style="margin-top:18px"><h2>Registered assets</h2>{% if assets %}<div class="table-wrap"><table><thead><tr><th>Title</th><th>Rights holder</th><th>Policy</th><th>License</th><th>Size</th><th>Status</th><th>Action</th></tr></thead><tbody>{% for a in assets %}<tr><td>{{ a['book_title'] }}</td><td>{{ a['rights_holder'] }}</td><td>{{ a['access_policy'] }}</td><td>{{ a['license_reference'] }}{% if a['license_expires_at'] %}<small><br>Until {{ a['license_expires_at'] }}</small>{% endif %}</td><td>{{ (a['file_size']/1048576)|round(2) }} MB</td><td>{{ a['license_status'] }}{% if not a['active'] %} · inactive{% endif %}</td><td><button class="btn ghost" type="button" onclick="setAudioLicense({{ a['book_id'] }},'{{ 'revoked' if a['license_status']=='active' else 'active' }}')">{{ 'Revoke' if a['license_status']=='active' else 'Reactivate' }}</button></td></tr>{% endfor %}</tbody></table></div>{% else %}<p class="muted">No audio assets registered yet.</p>{% endif %}</section>
    <script>
    document.getElementById('audioUploadForm').addEventListener('submit',async function(e){e.preventDefault();const form=e.currentTarget,btn=document.getElementById('audioSubmit'),out=document.getElementById('audioResult'),id=form.book_id.value;if(!id){out.textContent='Choose a catalog title first.';return}btn.disabled=true;btn.textContent='Uploading securely…';out.className='audio-status';try{const fd=new FormData(form);const res=await fetch('/api/admin/audiobooks/'+encodeURIComponent(id)+'/asset',{method:'POST',body:fd,credentials:'same-origin'});const data=await res.json();if(!res.ok)throw new Error(data.error||'Upload failed');out.className='audio-status ok';out.textContent='Audio registered. SHA-256: '+data.sha256+' · '+data.file_size+' bytes. Refreshing asset list…';setTimeout(()=>location.reload(),1000)}catch(err){out.className='audio-status err';out.textContent=String(err.message||err)}finally{btn.disabled=false;btn.textContent='Upload & register securely'}});
    async function setAudioLicense(id,status){if(!confirm('Change this audiobook license to '+status+'?'))return;const token=document.querySelector('input[name="_csrf"]')?.value;try{const r=await fetch('/api/admin/audiobooks/'+id+'/license-status',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':token||''},credentials:'same-origin',body:JSON.stringify({license_status:status})});const d=await r.json();if(!r.ok)throw new Error(d.error||'Request failed');location.reload()}catch(e){alert(e.message||'Could not update license')}}
    </script>
    '''
    return page('Audiobook Hosting & Licensing', html, books=books, assets=assets)


@bp.get('/api/audiobooks')
def list_audiobooks():
    """List only currently active licensed assets; never expose private object keys."""
    from app import db
    with db() as c:
        rows = c.execute("""SELECT a.book_id,b.title,b.author,b.genre,a.mime_type,a.file_size,
            a.access_policy,a.license_status,a.license_expires_at,a.active
            FROM audiobook_assets a JOIN books b ON b.id=a.book_id
            ORDER BY b.title LIMIT 500""").fetchall()
    items=[]
    for row in rows:
        if not _license_valid(row):
            continue
        items.append({'book_id':row['book_id'],'title':row['title'],'author':row['author'],
            'genre':row['genre'],
            'mime_type':row['mime_type'],'file_size':row['file_size'],'access_policy':row['access_policy'],
            'stream_url':f"/api/audiobooks/{row['book_id']}/stream"})
    return jsonify({'count':len(items),'audiobooks':items})


@bp.get('/api/audiobooks/<int:book_id>')
def audiobook_metadata(book_id):
    from app import db
    with db() as c:
        row = c.execute('''SELECT a.book_id,b.title,b.author,a.mime_type,a.file_size,a.access_policy,
            a.license_status,a.license_expires_at,a.active FROM audiobook_assets a JOIN books b ON b.id=a.book_id
            WHERE a.book_id=?''', (book_id,)).fetchone()
    available = bool(row and _license_valid(row))
    return jsonify({'book_id': book_id, 'title': row['title'] if row else None,
        'author': row['author'] if row else None, 'available': available,
        'access_policy': row['access_policy'] if available else 'unavailable',
        'stream_url': f'/api/audiobooks/{book_id}/stream' if available else None,
        'notice': None if available else 'No active, licensed audio asset is available.'})


@bp.post('/api/admin/audiobooks/<int:book_id>/asset')
def upload_audiobook_asset(book_id):
    _admin_user()
    # Global CSRF middleware validates the session token for this multipart request.
    upload = request.files.get('audio')
    rights_holder = (request.form.get('rights_holder') or '').strip()[:200]
    license_reference = (request.form.get('license_reference') or '').strip()[:200]
    policy = (request.form.get('access_policy') or 'licensed').strip()
    expires = (request.form.get('license_expires_at') or '').strip() or None
    if not upload or not upload.filename:
        return jsonify({'error': 'An audio file is required.'}), 400
    if not rights_holder or not license_reference:
        return jsonify({'error': 'Rights holder and license reference are required.'}), 400
    if policy not in ('sample', 'licensed'):
        return jsonify({'error': 'access_policy must be sample or licensed.'}), 400
    if expires:
        try:
            parsed_expiry = datetime.fromisoformat(expires.replace('Z', '+00:00'))
            if parsed_expiry.tzinfo is None:
                parsed_expiry = parsed_expiry.replace(tzinfo=timezone.utc)
            expires = parsed_expiry.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            return jsonify({'error': 'Invalid license expiry timestamp.'}), 400
    filename = upload.filename.replace('\\', '/').rsplit('/', 1)[-1]
    suffix = os.path.splitext(filename)[1].lower()
    if suffix not in AUDIO_TYPES:
        return jsonify({'error': 'Unsupported audio type. Use MP3, M4A, AAC, OGG, OPUS, WAV, FLAC or WEBM.'}), 415
    # Bounded read: rejects oversized uploads before any object is written.
    payload = upload.stream.read(MAX_AUDIO_BYTES + 1)
    if not payload:
        return jsonify({'error': 'The uploaded audio file is empty.'}), 400
    if len(payload) > MAX_AUDIO_BYTES:
        return jsonify({'error': f'Audio upload exceeds {MAX_AUDIO_BYTES // (1024*1024)} MB.'}), 413
    from upload_security import inspect_upload
    accepted, scan_status, scan_message = inspect_upload(filename, payload)
    if not accepted:
        code = 503 if scan_status == 'unavailable' else 415 if scan_status == 'invalid' else 400
        return jsonify({'error': scan_message, 'scan_status': scan_status}), code
    from app import db
    with db() as c:
        if not c.execute('SELECT 1 FROM books WHERE id=?', (book_id,)).fetchone():
            return jsonify({'error': 'Book not found.'}), 404
    key = f'audiobooks/{book_id}/{uuid.uuid4().hex}{suffix}'
    mime = AUDIO_TYPES[suffix]
    try:
        from cloud_storage import storage
        stored = storage.put_object(key, payload, content_type=mime)
    except Exception:
        current_app.logger.exception('Audiobook storage write failed')
        return jsonify({'error': 'Private audio storage is unavailable. Check storage configuration.'}), 503
    digest = hashlib.sha256(payload).hexdigest()
    try:
        with db() as c:
            c.execute('''INSERT INTO audiobook_assets(book_id,storage_key,original_name,mime_type,file_size,sha256_hex,
                rights_holder,license_reference,license_status,license_expires_at,access_policy,active,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                ON CONFLICT(book_id) DO UPDATE SET storage_key=excluded.storage_key,original_name=excluded.original_name,
                mime_type=excluded.mime_type,file_size=excluded.file_size,sha256_hex=excluded.sha256_hex,
                rights_holder=excluded.rights_holder,license_reference=excluded.license_reference,
                license_status=excluded.license_status,license_expires_at=excluded.license_expires_at,
                access_policy=excluded.access_policy,active=1,updated_at=CURRENT_TIMESTAMP''',
                (book_id,key,filename[:180],mime,len(payload),digest,rights_holder,license_reference,'active',expires,policy,1))
            # Ensure the catalog marks this as an audiobook product without exposing its asset publicly.
            c.execute('''INSERT INTO catalog_products(book_id,product_type,sale_enabled,digital_available,inventory_quantity,access_type)
                VALUES(?,'audiobook',1,1,0,'purchase') ON CONFLICT(book_id) DO UPDATE SET
                product_type='audiobook',digital_available=1,updated_at=CURRENT_TIMESTAMP''', (book_id,))
    except Exception:
        current_app.logger.exception('Audiobook metadata save failed; private object may need cleanup')
        return jsonify({'error': 'Audio was stored but metadata could not be saved. Ask an administrator to reconcile storage.'}), 500
    return jsonify({'status': 'stored', 'book_id': book_id, 'file_size': len(payload), 'sha256': digest,
        'license_status': 'active', 'access_policy': policy, 'scan_status': scan_status,
        'note': 'Rights holder and license reference are recorded; legal validity still depends on the underlying agreement.'}), 201


@bp.post('/api/admin/audiobooks/<int:book_id>/license-status')
def update_audiobook_license(book_id):
    _admin_user()
    data = request.get_json(silent=True) or {}
    status = data.get('license_status')
    if status not in ('active', 'expired', 'revoked'):
        return jsonify({'error': 'license_status must be active, expired, or revoked.'}), 400
    from app import db
    with db() as c:
        cur = c.execute('UPDATE audiobook_assets SET license_status=?,active=?,updated_at=CURRENT_TIMESTAMP WHERE book_id=?',
                         (status, 1 if status == 'active' else 0, book_id))
        if not cur.rowcount:
            return jsonify({'error': 'Audiobook asset not found.'}), 404
    return jsonify({'book_id': book_id, 'license_status': status, 'active': status == 'active'})


@bp.get('/api/audiobooks/<int:book_id>/stream')
def stream_audiobook(book_id):
    uid = session.get('uid')
    from app import db
    with db() as c:
        row = c.execute('SELECT * FROM audiobook_assets WHERE book_id=?', (book_id,)).fetchone()
        if not row or not _license_valid(row):
            abort(404)
        allowed = row['access_policy'] == 'sample'
        if type(uid) is int and uid > 0:
            from digital_entitlements import has_access
            allowed = allowed or has_access(c, uid, book_id)
        if not allowed:
            abort(403, description='Purchase or subscribe to access this licensed audiobook.')
        asset = dict(row)
    try:
        from cloud_storage import storage
        from flask import stream_with_context
        size = storage.object_size(asset['storage_key'])
    except Exception:
        current_app.logger.exception('Audiobook storage metadata read failed')
        abort(503, description='Audio storage is unavailable.')
    if size is None:
        abort(404)
    # A missing or changed object size is treated as an integrity/storage failure.
    if size != int(asset['file_size']) or size < 1:
        abort(503, description='Audio integrity verification failed.')
    range_header = request.headers.get('Range', '')
    start, end, status = 0, size - 1, 200
    if range_header:
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header.strip())
        if not match or (not match.group(1) and not match.group(2)):
            return '', 416, {'Content-Range': f'bytes */{size}'}
        if not match.group(1):
            suffix_len = int(match.group(2) or 0)
            if suffix_len <= 0:
                return '', 416, {'Content-Range': f'bytes */{size}'}
            start = max(0, size - suffix_len)
        else:
            start = int(match.group(1))
            if match.group(2): end = int(match.group(2))
        if start >= size or end < start:
            return '', 416, {'Content-Range': f'bytes */{size}'}
        end = min(end, size - 1)
        status = 206
    content_length = end - start + 1
    try:
        chunks = storage.iter_object_range(asset['storage_key'], start, end)
        response = current_app.response_class(stream_with_context(chunks), status=status, mimetype=asset['mime_type'], direct_passthrough=True)
    except Exception:
        current_app.logger.exception('Audiobook storage stream could not be opened')
        abort(503, description='Audio storage is unavailable.')
    response.headers['Accept-Ranges'] = 'bytes'
    response.headers['Content-Length'] = str(content_length)
    if status == 206:
        response.headers['Content-Range'] = f'bytes {start}-{end}/{size}'
    response.headers['Cache-Control'] = 'private, no-store, max-age=0'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Content-Disposition'] = 'inline'
    return response
