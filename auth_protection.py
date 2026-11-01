"""Small SQLite-backed login throttle, independent of Flask.

Uses a keyed digest so raw emails and IP addresses are not stored in the throttle table.
Expired throttle records are pruned during failed-login writes to keep the table bounded
by recent activity rather than retaining every identity ever seen.
"""
import hashlib
import hmac
import sqlite3
import time

WINDOW_SECONDS = 15 * 60
MAX_ATTEMPTS = 8

def identity_key(email, ip, secret):
    identity = (email or '').strip().lower() + '|' + (ip or '')
    return hmac.new(secret.encode(), identity.encode(), hashlib.sha256).hexdigest()

def initialize(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS auth_failures (identity TEXT PRIMARY KEY, attempts INTEGER NOT NULL, first_attempt INTEGER NOT NULL)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_auth_failures_first_attempt ON auth_failures(first_attempt)')

def blocked(conn, identity, now=None):
    now = int(time.time() if now is None else now)
    initialize(conn)
    row = conn.execute('SELECT attempts,first_attempt FROM auth_failures WHERE identity=?', (identity,)).fetchone()
    return bool(row and 0 <= now-row[1] < WINDOW_SECONDS and row[0] >= MAX_ATTEMPTS)

def failed(conn, identity, now=None):
    now = int(time.time() if now is None else now)
    initialize(conn)
    # Prune stale identities on the write path. The indexed timestamp keeps this
    # cleanup targeted as the throttle table grows.
    conn.execute('DELETE FROM auth_failures WHERE first_attempt <= ?', (now - WINDOW_SECONDS,))
    row = conn.execute('SELECT attempts,first_attempt FROM auth_failures WHERE identity=?', (identity,)).fetchone()
    if row and 0 <= now-row[1] < WINDOW_SECONDS:
        conn.execute('UPDATE auth_failures SET attempts=? WHERE identity=?', (row[0]+1,identity))
    else:
        conn.execute('INSERT INTO auth_failures(identity,attempts,first_attempt) VALUES(?,?,?) ON CONFLICT(identity) DO UPDATE SET attempts=excluded.attempts,first_attempt=excluded.first_attempt', (identity,1,now))
    conn.commit()

def clear(conn, identity):
    initialize(conn)
    conn.execute('DELETE FROM auth_failures WHERE identity=?', (identity,))
    conn.commit()
