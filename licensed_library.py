"""Local, license-gated text ingestion and evidence-based retrieval for LibraAI.

This is a provider-independent foundation, not a substitute for commercial LLMs,
OCR, publisher licensing, or a vector search service.
"""
import math
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from flask import Blueprint, abort, jsonify, request, session, render_template_string, redirect
from license_policy import license_is_active, license_allows_format

licensed = Blueprint('licensed', __name__)

def connect():
    from app import db
    return db()

def setup():
    c = connect()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS licensed_documents (
        id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL, title TEXT NOT NULL,
        rights_holder TEXT NOT NULL, license_reference TEXT NOT NULL,
        access_policy TEXT NOT NULL CHECK(access_policy IN ('sample','licensed')),
        created_at TEXT NOT NULL,
        license_valid_from TEXT, license_expires_at TEXT,
        license_territories TEXT NOT NULL DEFAULT '*', evidence_uri TEXT,
        license_status TEXT NOT NULL DEFAULT 'pending_review' CHECK(license_status IN ('pending_review','active','suspended','expired','revoked')),
        licensed_formats TEXT NOT NULL DEFAULT 'ebook', royalty_terms TEXT NOT NULL DEFAULT 'Not recorded');
    CREATE TABLE IF NOT EXISTS licensed_chunks (
        id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL,
        chunk_number INTEGER NOT NULL, content TEXT NOT NULL,
        FOREIGN KEY(document_id) REFERENCES licensed_documents(id));
    CREATE TABLE IF NOT EXISTS licensed_rights_audit (
        id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL,
        action TEXT NOT NULL, actor_user_id INTEGER, details TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(document_id) REFERENCES licensed_documents(id));
    CREATE INDEX IF NOT EXISTS idx_licensed_chunks_document ON licensed_chunks(document_id);
    ''')
    # Upgrade older databases without destructive table rebuilds.
    columns = {row['name'] for row in c.execute('PRAGMA table_info(licensed_documents)').fetchall()}
    additions = {
        'license_valid_from': 'TEXT', 'license_expires_at': 'TEXT',
        'license_territories': "TEXT NOT NULL DEFAULT '*'", 'evidence_uri': 'TEXT',
        'license_status': "TEXT NOT NULL DEFAULT 'pending_review'",
        'licensed_formats': "TEXT NOT NULL DEFAULT 'ebook'", 'royalty_terms': "TEXT NOT NULL DEFAULT 'Not recorded'",
    }
    for name, definition in additions.items():
        if name not in columns:
            c.execute(f'ALTER TABLE licensed_documents ADD COLUMN {name} {definition}')
    c.execute('CREATE INDEX IF NOT EXISTS idx_licensed_documents_book_status ON licensed_documents(book_id, license_status, access_policy)')
    c.commit(); c.close()

def chunk_text(text, max_words=180, overlap=25):
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Non-empty plain text required')
    if not 0 <= overlap < max_words:
        raise ValueError('Invalid overlap')
    words = text.split()
    step = max_words - overlap
    return [' '.join(words[i:i+max_words]) for i in range(0, len(words), step) if words[i:i+max_words]]

def tokens(text):
    return re.findall(r'[^\W_]+', text.lower(), flags=re.UNICODE)

def retrieve(question, rows, limit=5):
    """Deterministic BM25-style retrieval, returning evidence rather than invented answers."""
    terms = Counter(tokens(question))
    if not terms or not rows:
        return []
    documents = [Counter(tokens(row['content'])) for row in rows]
    lengths = [sum(d.values()) for d in documents]
    avg_len = sum(lengths) / len(lengths) or 1
    df = Counter(t for d in documents for t in d)
    results = []
    for row, doc, length in zip(rows, documents, lengths):
        score = 0.0
        for term, qtf in terms.items():
            if not doc[term]:
                continue
            idf = math.log(1 + (len(rows)-df[term]+0.5)/(df[term]+0.5))
            tf = doc[term]
            score += idf * (tf * 2.2)/(tf + 1.2*(0.25+0.75*length/avg_len)) * min(qtf, 3)
        if score > 0:
            results.append({'document_id':row['document_id'], 'chunk':row['chunk_number'],
                            'title':row['title'], 'excerpt':row['content'][:700],
                            'score':round(score, 4)})
    return sorted(results, key=lambda x: x['score'], reverse=True)[:limit]

def admin_required():
    from app import current_user
    user = current_user()
    if not user:
        abort(401)
    if user['role'] != 'admin':
        abort(403)

@licensed.route('/admin/licensed-content', methods=['GET','POST'])
def manage_licensed_content():
    admin_required()
    from app import page
    if request.method == 'POST':
        data = request.form
        try:
            book_id = int(data.get('book_id', ''))
        except ValueError:
            abort(400)
        title = data.get('title','').strip()[:200]
        holder = data.get('rights_holder','').strip()[:200]
        license_ref = data.get('license_reference','').strip()[:200]
        policy = data.get('access_policy','')
        content = data.get('content','')
        if not all([title, holder, license_ref, content.strip()]) or policy not in ('sample','licensed') or len(content)>200000:
            abort(400, 'Document, permission reference and valid access policy required')
        c=connect()
        if not c.execute('SELECT 1 FROM books WHERE id=?',(book_id,)).fetchone():
            c.close();abort(404)
        valid_from = data.get('license_valid_from','').strip() or None
        expires_at = data.get('license_expires_at','').strip() or None
        territories = data.get('license_territories','*').strip().upper() or '*'
        evidence_uri = data.get('evidence_uri','').strip()[:500] or None
        royalty_terms = data.get('royalty_terms','').strip()[:500]
        format_parts = [part.strip().lower() for part in data.get('licensed_formats','ebook').split(',')]
        allowed_formats = {'ebook','audiobook','print','manga','sample'}
        if not royalty_terms or not format_parts or any(part not in allowed_formats for part in format_parts):
            c.close(); abort(400, 'Record royalty terms and valid licensed formats')
        licensed_formats = ','.join(sorted(set(format_parts)))
        for date_value in (valid_from, expires_at):
            if date_value:
                try: datetime.strptime(date_value, '%Y-%m-%d')
                except ValueError:
                    c.close(); abort(400, 'License dates must use YYYY-MM-DD')
        if valid_from and expires_at and valid_from >= expires_at:
            c.close(); abort(400, 'License expiry must be after its start date')
        territory_parts = [part.strip() for part in territories.split(',')]
        if (not territory_parts or any(not part for part in territory_parts)
            or ('*' in territory_parts and len(territory_parts) > 1)
            or any(part != '*' and (not part.isalpha() or len(part) != 2) for part in territory_parts)):
            c.close(); abort(400, 'Territories must be * or comma-separated two-letter ISO country codes')
        cur=c.execute("""INSERT INTO licensed_documents(book_id,title,rights_holder,license_reference,access_policy,created_at,license_valid_from,license_expires_at,license_territories,evidence_uri,license_status,licensed_formats,royalty_terms)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (book_id,title,holder,license_ref,policy,datetime.now(timezone.utc).isoformat(),valid_from,expires_at,territories,evidence_uri,'pending_review',licensed_formats,royalty_terms))
        c.executemany('INSERT INTO licensed_chunks(document_id,chunk_number,content) VALUES(?,?,?)',
            [(cur.lastrowid,i,chunk) for i,chunk in enumerate(chunk_text(content))])
        c.execute('INSERT INTO licensed_rights_audit(document_id,action,actor_user_id,details,created_at) VALUES(?,?,?,?,?)',
            (cur.lastrowid,'created_pending_review',session.get('uid'),f'access_policy={policy}; formats={licensed_formats}; territories={territories}; expiry={expires_at or "none"}; royalty_terms_recorded=yes',datetime.now(timezone.utc).isoformat()))
        c.commit();c.close()
    c=connect(); docs=c.execute('SELECT d.*,b.title AS book_title FROM licensed_documents d JOIN books b ON b.id=d.book_id ORDER BY d.id DESC').fetchall(); rights_events=c.execute('SELECT a.*,d.title AS document_title FROM licensed_rights_audit a JOIN licensed_documents d ON d.id=a.document_id ORDER BY a.id DESC LIMIT 100').fetchall();c.close()
    return page('Licensed content','''<style>
    .lic-hero{padding:28px;border-radius:22px;color:#fff;background:radial-gradient(circle at 85% 15%,#67d6ff66,transparent 28%),linear-gradient(120deg,#211c83,#5145e8 58%,#9165ff);margin-bottom:20px;box-shadow:0 16px 40px #4338ca24}
    .lic-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:15px;margin:16px 0}.lic-card{background:linear-gradient(145deg,#fff,#faf9ff);border:1px solid #e5e6ff;border-radius:18px;padding:18px;box-shadow:0 10px 28px #3542a20b;transition:transform .18s,box-shadow .18s}.lic-card:hover{transform:translateY(-3px);box-shadow:0 16px 34px #4338ca18}.lic-card label{display:block;font-size:13px;font-weight:700;color:#4b5573;margin-top:8px}.lic-badge{display:inline-block;border-radius:99px;padding:5px 9px;background:#eeedff;color:#5145cd;font-size:11px;font-weight:800}.lic-note{padding:13px 15px;background:#f0f4ff;border:1px solid #dfe6ff;border-radius:13px;color:#4c5b83;font-size:13px;line-height:1.55}body.midnight .lic-card{background:#111b37;border-color:#29375f}body.midnight .lic-card label{color:#c5cdec}body.midnight .lic-note{background:#1a2850;color:#cbd7ff;border-color:#344578}
    </style><section class="lic-hero"><span class="lic-badge">Rights-aware library</span><h1>Licensed content workspace</h1><p>Manage text that LibraAI is authorized to display and process. Each record requires a rights holder, license reference and explicit access policy.</p></section><div class="lic-note"><b>Rights & privacy reminder:</b> only upload content you are authorized to process. “Licensed access” is not a substitute for entitlement checks, publisher agreements or legal review.</div><div class="lic-grid"><section class="lic-card"><h2>Add authorized document</h2><form method="post"><label>Book ID</label><input class="input" type="number" min="1" name="book_id" required><label>Document title</label><input class="input" name="title" maxlength="200" required><label>Rights holder</label><input class="input" name="rights_holder" maxlength="200" required><label>License reference</label><input class="input" name="license_reference" maxlength="200" required><label>Valid from (optional)</label><input class="input" type="date" name="license_valid_from"><label>Expires on (optional)</label><input class="input" type="date" name="license_expires_at"><label>Allowed territories (ISO codes, comma separated; * means all)</label><input class="input" name="license_territories" maxlength="200" value="*" required><label>Evidence URI/reference (optional; internal reference only)</label><input class="input" name="evidence_uri" maxlength="500"><label>Licensed formats (comma-separated: ebook,audiobook,print,manga)</label><input class="input" name="licensed_formats" maxlength="120" value="ebook" required><label>Royalty terms/reference</label><input class="input" name="royalty_terms" maxlength="500" required><label>Access policy</label><select class="input" name="access_policy"><option value="sample">Public sample</option><option value="licensed">Licensed access</option></select><label>Authorized text</label><textarea class="input" name="content" rows="9" maxlength="200000" required placeholder="Paste authorized text here…"></textarea><button class="btn" type="submit">Save document & index text</button></form></section><section class="lic-card"><h2>Content readiness</h2><p class="muted">Documents are split into searchable chunks for evidence retrieval. The current implementation is local and deterministic; it does not generate an LLM answer.</p><p><span class="lic-badge">Evidence-first retrieval</span> <span class="lic-badge">Access-policy aware</span></p><p class="muted">For a licensed document, a signed-in user must also have the appropriate book entitlement before its text can be used as research evidence.</p><a class="btn ghost" href="/research/">Open Research Lab</a></section></div><section class="lic-card"><div class="row between"><h2>Indexed documents</h2><span class="lic-badge">{{ docs|length }} records</span></div>{% if docs %}<div class="grid">{% for d in docs %}<article class="lic-card"><span class="lic-badge">{{ d['access_policy']|title }}</span><h3 style="margin-top:10px">{{ d['title'] }}</h3><p class="muted">{{ d['book_title'] }}</p><p><b>Rights holder:</b> {{ d['rights_holder'] }}</p><p class="muted small">License ref: {{ d['license_reference'] }}</p><p class="muted small">Formats: {{ d['licensed_formats'] }} · Territories: {{ d['license_territories'] }} · Expires: {{ d['license_expires_at'] or 'No recorded expiry' }} · Status: {{ d['license_status'] }}</p><p class="muted small">Royalty terms: {{ d['royalty_terms'] }} · Evidence: {{ d['evidence_uri'] or 'Not recorded' }}</p><form method="post" action="/admin/licensed-content/{{ d['id'] }}/status"><label>Review decision</label><select class="input" name="license_status"><option value="active">Approve / activate</option><option value="suspended">Suspend</option><option value="revoked">Revoke</option><option value="pending_review">Pending review</option></select><label>Review note</label><input class="input" name="review_note" maxlength="300" required><button class="btn ghost" type="submit">Record review</button></form></article>{% endfor %}</div>{% else %}<div class="gap-empty">No licensed documents have been added yet.</div>{% endif %}</section><section class="lic-card"><div class="row between"><h2>Rights audit trail</h2><span class="lic-badge">Latest {{ rights_events|length }} events</span></div>{% if rights_events %}<div class="table-wrap"><table><thead><tr><th>When</th><th>Document</th><th>Action</th><th>Actor ID</th><th>Details</th></tr></thead><tbody>{% for event in rights_events %}<tr><td>{{ event['created_at'] }}</td><td>{{ event['document_title'] }}</td><td>{{ event['action'] }}</td><td>{{ event['actor_user_id'] }}</td><td>{{ event['details'] }}</td></tr>{% endfor %}</tbody></table></div>{% else %}<div class="gap-empty">No rights review events yet.</div>{% endif %}</section>''',docs=docs,rights_events=rights_events,csrf=session.get('_csrf',''))

@licensed.post('/admin/licensed-content/<int:document_id>/status')
def review_licensed_content(document_id):
    admin_required()
    status = request.form.get('license_status', '').strip().lower()
    note = request.form.get('review_note', '').strip()[:300]
    if status not in ('pending_review', 'active', 'suspended', 'revoked') or not note:
        abort(400, 'Valid review status and note are required')
    c = connect()
    row = c.execute('SELECT id,license_status FROM licensed_documents WHERE id=?', (document_id,)).fetchone()
    if not row:
        c.close(); abort(404)
    old_status = row['license_status']
    c.execute('UPDATE licensed_documents SET license_status=? WHERE id=?', (status, document_id))
    c.execute('INSERT INTO licensed_rights_audit(document_id,action,actor_user_id,details,created_at) VALUES(?,?,?,?,?)',
              (document_id, 'status_changed', session.get('uid'), f'{old_status}->{status}; note={note}', datetime.now(timezone.utc).isoformat()))
    c.commit(); c.close()
    return redirect('/admin/licensed-content', code=303)


@licensed.get('/api/research/evidence')
def research_evidence():
    from app import current_user
    question=request.args.get('q','').strip()
    if not question or len(question)>500:
        abort(400)
    c=connect()
    rows=c.execute('''SELECT d.id AS document_id,d.title,d.book_id,d.access_policy,
        ch.chunk_number,ch.content FROM licensed_chunks ch JOIN licensed_documents d ON d.id=ch.document_id
        ORDER BY d.id,ch.chunk_number LIMIT 10000''').fetchall()
    user=current_user()
    # Authentication alone must NEVER reveal licensed content.
    from digital_entitlements import has_access
    current_time = datetime.now(timezone.utc)
    visible=[]
    trusted_territory = session.get('verified_territory')
    for row in rows:
        doc = dict(row)
        # Legacy schemas migrate with safe defaults; expired/revoked/future rights
        # never enter retrieval even if the user has an entitlement. Restricted
        # territories require a verified account/session territory; no IP guess.
        if not license_is_active(doc, now=current_time, territory=trusted_territory):
            continue
        if not (license_allows_format(doc, 'ebook') or (doc['access_policy'] == 'sample' and license_allows_format(doc, 'sample'))):
            continue
        if doc['access_policy']=='sample' or (user is not None and has_access(c,user['id'],doc['book_id'])):
            visible.append(doc)
    c.close()
    return jsonify({'question':question,'evidence':retrieve(question,visible),
                    'answer_status':'evidence_only','notice':'Excerpts are retrieved from locally uploaded, rights-asserted documents. No LLM answer is generated.'})
