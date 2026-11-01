"""Private, licensed eBook file delivery. Files never live under Flask static directories."""
import os
import hashlib
import hmac
import re
from pathlib import Path
from digital_entitlements import has_access

SAFE_NAME = re.compile(r'\A[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}\Z')
MIMES = {'.pdf': 'application/pdf', '.epub': 'application/epub+zip'}


def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS ebook_files (
        book_id INTEGER PRIMARY KEY, stored_name TEXT NOT NULL UNIQUE,
        original_name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
        FOREIGN KEY(book_id) REFERENCES books(id))''')
    columns = {row[1] for row in conn.execute('PRAGMA table_info(ebook_files)')}
    if 'sha256_hex' not in columns:
        conn.execute('ALTER TABLE ebook_files ADD COLUMN sha256_hex TEXT')
    conn.commit()


def verify_file_digest(path, expected):
    """Check the configured immutable upload checksum before serving licensed content."""
    if not isinstance(expected, str) or len(expected) != 64 or any(c not in '0123456789abcdefABCDEF' for c in expected):
        raise ValueError('Missing or invalid SHA-256 checksum')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    if not hmac.compare_digest(digest.hexdigest(), expected.lower()):
        raise ValueError('eBook integrity verification failed')
    return True


def private_file(root, stored_name):
    if not isinstance(stored_name, str) or not SAFE_NAME.fullmatch(stored_name):
        raise ValueError('Invalid stored filename')
    suffix = Path(stored_name).suffix.lower()
    if suffix not in MIMES:
        raise ValueError('Unsupported digital format')
    base = Path(root).resolve(strict=True)
    target = (base / stored_name).resolve(strict=True)
    if target.parent != base or not target.is_file():
        raise ValueError('File outside private library')
    return target, MIMES[suffix]


def safe_download_name(original_name, book_id, suffix):
    """Return a safe display filename without trusting POSIX-only path parsing.

    Catalogue metadata may have been created on Windows or imported from another
    system, so both slash styles are treated as path separators. Control characters
    are removed before the name reaches Content-Disposition.
    """
    fallback = f'book-{int(book_id)}{suffix.lower()}'
    if not isinstance(original_name, str) or not isinstance(suffix, str):
        return fallback
    name = original_name.replace('\\', '/').rsplit('/', 1)[-1]
    name = ''.join(ch for ch in name if ch.isprintable()).strip(' .')
    if not name or len(name) > 180 or name in ('.', '..'):
        return fallback
    if Path(name).suffix.lower() != suffix.lower():
        return fallback
    return name


def register(app, connect):
    from flask import abort, current_app, send_file, session
    with connect() as conn:
        setup(conn)

    @app.get('/api/ebooks/<int:book_id>/download')
    def ebook_download(book_id):
        uid = session.get('uid')
        if type(uid) is not int or uid <= 0 or book_id <= 0:
            abort(403)
        with connect() as conn:
            if not has_access(conn, uid, book_id):
                abort(403)
            row = conn.execute('SELECT stored_name,original_name,sha256_hex FROM ebook_files WHERE book_id=? AND active=1', (book_id,)).fetchone()
            if row is None:
                abort(404)
            stored_name, original_name, checksum = row['stored_name'], row['original_name'], row['sha256_hex']
        root = current_app.config.get('LIBRAAI_PRIVATE_EBOOK_DIR') or os.environ.get('LIBRAAI_PRIVATE_EBOOK_DIR')
        if not root:
            abort(503, description='Private ebook storage is not configured')
        try:
            path, mime = private_file(root, stored_name)
            # In production, unverified legacy file mappings must be migrated first.
            if checksum is not None or current_app.config.get('LIBRAAI_ENV') == 'production' or os.environ.get('LIBRAAI_ENV') == 'production':
                verify_file_digest(path, checksum)
        except (OSError, ValueError):
            abort(404)
        download_name = safe_download_name(original_name, book_id, path.suffix)
        response = send_file(path, mimetype=mime, as_attachment=True, download_name=download_name,
                             conditional=False, max_age=0)
        response.headers['Cache-Control'] = 'private, no-store, max-age=0'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'none'; sandbox"
        return response
