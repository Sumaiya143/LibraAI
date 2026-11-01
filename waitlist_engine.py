"""Transactional, FIFO library waitlist with expiring offers."""
import sqlite3
from datetime import datetime, timedelta, timezone

class WaitlistError(ValueError): pass

def now_iso(): return datetime.now(timezone.utc).isoformat(timespec='seconds')

def setup(conn):
    conn.executescript('''CREATE TABLE IF NOT EXISTS book_waitlist (
      id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, book_id INTEGER NOT NULL,
      status TEXT NOT NULL DEFAULT 'waiting' CHECK(status IN ('waiting','offered','accepted','cancelled','expired')),
      joined_at TEXT NOT NULL, offered_at TEXT, expires_at TEXT, accepted_at TEXT);
      CREATE UNIQUE INDEX IF NOT EXISTS waitlist_one_active ON book_waitlist(user_id,book_id)
      WHERE status IN ('waiting','offered');
      CREATE INDEX IF NOT EXISTS waitlist_queue ON book_waitlist(book_id,status,joined_at,id);
    ''')

def join(conn,user_id,book_id):
    if not conn.execute('SELECT 1 FROM users WHERE id=?',(user_id,)).fetchone(): raise WaitlistError('Unknown reader')
    if not conn.execute('SELECT 1 FROM books WHERE id=?',(book_id,)).fetchone(): raise WaitlistError('Unknown book')
    try:
        cur=conn.execute('INSERT INTO book_waitlist(user_id,book_id,joined_at) VALUES(?,?,?)',(user_id,book_id,now_iso()))
        return cur.lastrowid
    except sqlite3.IntegrityError as e: raise WaitlistError('Already waiting or offered this book') from e

def cancel(conn,user_id,entry_id):
    cur=conn.execute("UPDATE book_waitlist SET status='cancelled' WHERE id=? AND user_id=? AND status IN ('waiting','offered')",(entry_id,user_id))
    if cur.rowcount!=1: raise WaitlistError('Active entry not found')

def expire(conn):
    return conn.execute("UPDATE book_waitlist SET status='expired' WHERE status='offered' AND expires_at<=?",(now_iso(),)).rowcount

def offer_next(conn,book_id,days=2):
    if not 1<=days<=14: raise WaitlistError('Offer expiry must be 1–14 days')
    expire(conn)
    if conn.execute("SELECT 1 FROM book_waitlist WHERE book_id=? AND status='offered'",(book_id,)).fetchone():
        raise WaitlistError('An offer is already active for this book')
    row=conn.execute("SELECT id FROM book_waitlist WHERE book_id=? AND status='waiting' ORDER BY joined_at,id LIMIT 1",(book_id,)).fetchone()
    if row is None: return None
    until=(datetime.now(timezone.utc)+timedelta(days=days)).isoformat(timespec='seconds')
    conn.execute("UPDATE book_waitlist SET status='offered',offered_at=?,expires_at=? WHERE id=?",(now_iso(),until,row[0]))
    return row[0]

def accept(conn,user_id,entry_id):
    expire(conn)
    row=conn.execute("SELECT book_id FROM book_waitlist WHERE id=? AND user_id=? AND status='offered'",(entry_id,user_id)).fetchone()
    if row is None: raise WaitlistError('No valid offer for this reader')
    conn.execute("UPDATE book_waitlist SET status='accepted',accepted_at=? WHERE id=?",(now_iso(),entry_id))
    return row[0]
