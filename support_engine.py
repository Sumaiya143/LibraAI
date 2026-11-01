"""SQLite-backed customer support ticket operations. No external services required."""
import sqlite3
from datetime import datetime, timezone

STATUSES = {'open', 'in_progress', 'resolved', 'closed'}
CATEGORIES = {'account', 'reading', 'payment', 'library', 'technical', 'other'}

def setup(conn):
    # Create current tables first, then safely upgrade older prototype databases.
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS support_tickets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      subject TEXT NOT NULL,
      category TEXT NOT NULL DEFAULT 'other',
      status TEXT NOT NULL DEFAULT 'open',
      created_at TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL DEFAULT '',
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS support_messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ticket_id INTEGER NOT NULL,
      author_id INTEGER NOT NULL,
      body TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY(ticket_id) REFERENCES support_tickets(id),
      FOREIGN KEY(author_id) REFERENCES users(id)
    );
    CREATE INDEX IF NOT EXISTS idx_support_messages_ticket ON support_messages(ticket_id, id);
    """)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(support_tickets)")}
    if 'category' not in cols:
        conn.execute("ALTER TABLE support_tickets ADD COLUMN category TEXT NOT NULL DEFAULT 'other'")
    if 'created_at' not in cols:
        conn.execute("ALTER TABLE support_tickets ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
    if 'updated_at' not in cols:
        conn.execute("ALTER TABLE support_tickets ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
    # Legacy prototype used `created`; preserve existing ticket timestamps.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(support_tickets)")}
    if 'created' in cols:
        conn.execute("UPDATE support_tickets SET created_at=created WHERE created_at='' OR created_at IS NULL")
    conn.execute("UPDATE support_tickets SET updated_at=created_at WHERE updated_at='' OR updated_at IS NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_support_owner ON support_tickets(user_id, updated_at)")

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def validate_text(value, minimum, maximum, field):
    value = (value or '').strip()
    if not minimum <= len(value) <= maximum or any(ord(c)<32 and c not in '\n\t' for c in value):
        raise ValueError(f'{field} must contain {minimum}-{maximum} valid characters')
    return value

def create_ticket(conn, user_id, subject, category, body):
    subject = validate_text(subject, 5, 140, 'Subject')
    body = validate_text(body, 10, 5000, 'Message')
    if category not in CATEGORIES: raise ValueError('Invalid category')
    stamp = now()
    with conn:
        cur = conn.execute('INSERT INTO support_tickets(user_id,subject,category,status,created_at,updated_at) VALUES(?,?,?,?,?,?)',
                           (user_id, subject, category, 'open', stamp, stamp))
        conn.execute('INSERT INTO support_messages(ticket_id,author_id,body,created_at) VALUES(?,?,?,?)',
                     (cur.lastrowid, user_id, body, stamp))
    return cur.lastrowid

def get_ticket(conn, ticket_id, user_id, is_admin=False):
    ticket = conn.execute('SELECT * FROM support_tickets WHERE id=?', (ticket_id,)).fetchone()
    if ticket is None or (not is_admin and ticket['user_id'] != user_id):
        return None
    return ticket

def add_message(conn, ticket_id, user_id, body, is_admin=False):
    body = validate_text(body, 1, 5000, 'Message')
    ticket = get_ticket(conn, ticket_id, user_id, is_admin)
    if ticket is None: raise PermissionError('Ticket not found')
    if ticket['status'] == 'closed': raise ValueError('Closed tickets cannot receive messages')
    stamp = now()
    with conn:
        conn.execute('INSERT INTO support_messages(ticket_id,author_id,body,created_at) VALUES(?,?,?,?)',
                     (ticket_id,user_id,body,stamp))
        conn.execute('UPDATE support_tickets SET updated_at=? WHERE id=?', (stamp,ticket_id))

def change_status(conn, ticket_id, status, admin):
    if not admin: raise PermissionError('Admin required')
    if status not in STATUSES: raise ValueError('Invalid status')
    with conn:
        cur = conn.execute('UPDATE support_tickets SET status=?,updated_at=? WHERE id=?', (status,now(),ticket_id))
    if cur.rowcount == 0: raise LookupError('Ticket not found')
