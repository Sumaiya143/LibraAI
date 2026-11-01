"""SQLite-backed server-side Flask sessions for single-host deployments.

The browser receives only a signed opaque session identifier. Session contents
stay in SQLite. Use PostgreSQL/Redis-backed sessions for multi-host deployments.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from flask.sessions import SessionInterface, SessionMixin
from itsdangerous import BadSignature, URLSafeSerializer
from werkzeug.datastructures import CallbackDict


class SQLiteSession(CallbackDict, SessionMixin):
    def __init__(self, initial: dict[str, Any] | None = None, *, sid: str | None = None,
                 new: bool = False):
        def on_update(_):
            self.modified = True
        super().__init__(initial or {}, on_update)
        self.sid = sid or secrets.token_urlsafe(32)
        self.new = new
        self.modified = False
        self.regenerate = False

    def clear(self) -> None:
        super().clear()
        self.regenerate = True
        self.modified = True


class SQLiteSessionInterface(SessionInterface):
    """Server-side sessions with signed opaque IDs, TTL, and ID rotation on clear."""
    session_class = SQLiteSession
    salt = "libraai.server-side-session.v1"

    def __init__(self, database_path: str):
        self.database_path = database_path
        if database_path in (":memory:", "") or database_path.startswith("file:"):
            raise RuntimeError("Server-side sessions require a persistent SQLite file path.")
        parent = os.path.dirname(os.path.abspath(database_path))
        os.makedirs(parent, mode=0o750, exist_ok=True)
        self._initialize()

    def _connect(self):
        conn = sqlite3.connect(self.database_path, timeout=15)
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self):
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""CREATE TABLE IF NOT EXISTS server_sessions (
                session_id TEXT PRIMARY KEY,
                session_data TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_server_sessions_expiry ON server_sessions(expires_at)")

    def _serializer(self, app):
        return URLSafeSerializer(app.secret_key, salt=self.salt)

    def open_session(self, app, request):
        cookie_name = self.get_cookie_name(app)
        signed_sid = request.cookies.get(cookie_name)
        if not signed_sid:
            return self.session_class(new=True)
        try:
            sid = self._serializer(app).loads(signed_sid)
        except (BadSignature, TypeError, ValueError):
            return self.session_class(new=True)
        if not isinstance(sid, str) or len(sid) > 128:
            return self.session_class(new=True)
        now = int(time.time())
        try:
            with self._connection() as conn:
                row = conn.execute(
                    "SELECT session_data, expires_at FROM server_sessions WHERE session_id=?", (sid,)
                ).fetchone()
                if row is None:
                    return self.session_class(new=True)
                if int(row[1]) <= now:
                    conn.execute("DELETE FROM server_sessions WHERE session_id=?", (sid,))
                    return self.session_class(new=True)
                data = json.loads(row[0])
                if not isinstance(data, dict):
                    conn.execute("DELETE FROM server_sessions WHERE session_id=?", (sid,))
                    return self.session_class(new=True)
                return self.session_class(data, sid=sid, new=False)
        except (sqlite3.Error, json.JSONDecodeError, OSError) as exc:
            # Fail closed rather than silently switching to client-side sessions.
            app.logger.exception("Server-side session storage unavailable")
            raise RuntimeError("LibraAI session storage is unavailable") from exc

    def save_session(self, app, session, response):
        cookie_name = self.get_cookie_name(app)
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        secure = self.get_cookie_secure(app)
        httponly = self.get_cookie_httponly(app)
        samesite = self.get_cookie_samesite(app)
        now = int(time.time())

        if not session:
            if session.modified and getattr(session, "sid", None):
                with self._connection() as conn:
                    conn.execute("DELETE FROM server_sessions WHERE session_id=?", (session.sid,))
                response.delete_cookie(cookie_name, domain=domain, path=path,
                                       secure=secure, httponly=httponly, samesite=samesite)
            return

        if session.regenerate or session.new:
            old_sid = session.sid
            session.sid = secrets.token_urlsafe(32)
            session.new = False
            session.regenerate = False
            if old_sid:
                with self._connection() as conn:
                    conn.execute("DELETE FROM server_sessions WHERE session_id=?", (old_sid,))

        max_age = int(app.permanent_session_lifetime.total_seconds())
        expires_at = now + max_age
        try:
            payload = json.dumps(dict(session), separators=(",", ":"), ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Session contains a non-serializable value") from exc
        try:
            with self._connection() as conn:
                conn.execute("""INSERT INTO server_sessions
                    (session_id,session_data,created_at,updated_at,expires_at)
                    VALUES(?,?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET
                    session_data=excluded.session_data, updated_at=excluded.updated_at,
                    expires_at=excluded.expires_at""",
                    (session.sid, payload, now, now, expires_at))
                # Opportunistic bounded cleanup, avoiding an unbounded scan each request.
                if now % 97 == 0:
                    conn.execute("DELETE FROM server_sessions WHERE expires_at<=?", (now,))
        except sqlite3.Error as exc:
            app.logger.exception("Could not persist server-side session")
            raise RuntimeError("LibraAI session could not be saved") from exc

        signed_sid = self._serializer(app).dumps(session.sid)
        cookie_expires = self.get_expiration_time(app, session) if session.permanent else None
        response.set_cookie(cookie_name, signed_sid, expires=cookie_expires,
                            httponly=httponly, secure=secure, samesite=samesite,
                            domain=domain, path=path)
