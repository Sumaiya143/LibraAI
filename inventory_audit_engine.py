"""Inventory reconciliation engine; pure Python and SQLite, independent of Flask."""
import sqlite3
from datetime import datetime, timezone

SCHEMA = '''
CREATE TABLE IF NOT EXISTS stock_audits (
 id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL, expected INTEGER NOT NULL,
 counted INTEGER NOT NULL, difference INTEGER NOT NULL, note TEXT NOT NULL,
 actor_id INTEGER NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(book_id) REFERENCES books(id));
'''


def setup(conn):
    conn.executescript(SCHEMA)


def record_count(conn, *, book_id, counted, actor_id, note='', apply=False):
    """Record a physical stock count. Adjust stock only when explicitly approved."""
    if not isinstance(counted, int) or isinstance(counted, bool) or counted < 0:
        raise ValueError('Count must be a non-negative integer')
    if not isinstance(actor_id, int) or actor_id < 1:
        raise ValueError('Invalid auditor')
    if len(note) > 1000:
        raise ValueError('Note too long')
    conn.execute('SAVEPOINT stock_count')
    try:
        book = conn.execute('SELECT id, stock FROM books WHERE id=?', (book_id,)).fetchone()
        if book is None:
            raise ValueError('Book not found')
        expected = int(book[1]); difference = counted - expected
        created = datetime.now(timezone.utc).isoformat()
        cur = conn.execute('''INSERT INTO stock_audits
            (book_id,expected,counted,difference,note,actor_id,created_at)
            VALUES (?,?,?,?,?,?,?)''',
            (book_id, expected, counted, difference, note, actor_id, created))
        if apply:
            conn.execute('UPDATE books SET stock=? WHERE id=?', (counted, book_id))
        conn.execute('RELEASE SAVEPOINT stock_count')
        return {'id':cur.lastrowid,'expected':expected,'counted':counted,
                'difference':difference,'applied':bool(apply)}
    except Exception:
        conn.execute('ROLLBACK TO SAVEPOINT stock_count')
        conn.execute('RELEASE SAVEPOINT stock_count')
        raise
