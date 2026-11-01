"""Qualified reading events and abuse-resistant catalog rankings.

The server records authenticated reading activity; clients cannot submit arbitrary
reader IDs. Events are throttled and deduplicated. This is a local fraud-mitigation
foundation, not a guarantee against coordinated abuse.
"""
import sqlite3
from datetime import datetime, timezone, timedelta

SCHEMA = '''
CREATE TABLE IF NOT EXISTS qualified_reading_events (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, book_id INTEGER NOT NULL,
 event_type TEXT NOT NULL CHECK(event_type IN ('session','completion')),
 recorded_at TEXT NOT NULL,
 UNIQUE(user_id, book_id, event_type, recorded_at)
);
CREATE INDEX IF NOT EXISTS qre_book_time ON qualified_reading_events(book_id, recorded_at);
CREATE INDEX IF NOT EXISTS qre_user_time ON qualified_reading_events(user_id, recorded_at);
'''

def setup(conn):
    conn.executescript(SCHEMA)

def record(conn, user_id, book_id, event_type='session', now=None):
    if event_type not in ('session','completion'):
        raise ValueError('Unsupported event type')
    if not isinstance(user_id, int) or not isinstance(book_id, int) or user_id < 1 or book_id < 1:
        raise ValueError('Invalid user or book')
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Timezone-aware time required')
    stamp = now.astimezone(timezone.utc).isoformat()
    cutoff = (now - timedelta(minutes=20 if event_type == 'session' else 365*24*60)).astimezone(timezone.utc).isoformat()
    existing = conn.execute('''SELECT 1 FROM qualified_reading_events
        WHERE user_id=? AND book_id=? AND event_type=? AND recorded_at>=? LIMIT 1''',
        (user_id, book_id, event_type, cutoff)).fetchone()
    if existing:
        return False
    conn.execute('INSERT INTO qualified_reading_events(user_id,book_id,event_type,recorded_at) VALUES(?,?,?,?)',
                 (user_id, book_id, event_type, stamp))
    return True

def leaderboard(conn, days=30, limit=20, now=None):
    if not isinstance(days, int) or not 1 <= days <= 365:
        raise ValueError('days must be 1..365')
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError('limit must be 1..100')
    now = now or datetime.now(timezone.utc)
    cutoff = (now-timedelta(days=days)).astimezone(timezone.utc).isoformat()
    rows = conn.execute('''SELECT book_id,
      COUNT(DISTINCT CASE WHEN event_type='session' THEN user_id END) unique_readers,
      COUNT(CASE WHEN event_type='session' THEN 1 END) sessions,
      COUNT(DISTINCT CASE WHEN event_type='completion' THEN user_id END) completions
      FROM qualified_reading_events WHERE recorded_at>=? GROUP BY book_id''', (cutoff,)).fetchall()
    result = [dict(book_id=r[0], unique_readers=r[1], sessions=r[2], completions=r[3],
                   score=round(r[1]*3 + min(r[2], r[1]*10)*0.3 + r[3]*5, 2)) for r in rows]
    return sorted(result, key=lambda r:(-r['score'],r['book_id']))[:limit]
