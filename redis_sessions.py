"""Redis-backed server-side Flask sessions for multi-worker deployments.

Redis must be private-network-only, authenticated, TLS-enabled when crossing
untrusted networks, and configured with an eviction policy suitable for sessions.
"""
from __future__ import annotations
import json, secrets, time
from typing import Any
from flask.sessions import SessionInterface, SessionMixin
from itsdangerous import BadSignature, URLSafeSerializer
from werkzeug.datastructures import CallbackDict

class RedisSession(CallbackDict, SessionMixin):
    def __init__(self, initial: dict[str, Any] | None = None, *, sid: str | None = None, new: bool = False):
        def on_update(_): self.modified = True
        super().__init__(initial or {}, on_update)
        self.sid = sid or secrets.token_urlsafe(32)
        self.new = new
        self.modified = False
        self.regenerate = False
    def clear(self):
        super().clear(); self.regenerate = True; self.modified = True

class RedisSessionInterface(SessionInterface):
    session_class = RedisSession
    salt = 'libraai.redis-server-side-session.v1'
    def __init__(self, redis_url: str, prefix: str = 'libraai:sess:'):
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError('Redis session backend selected but redis package is not installed.') from exc
        self.client = redis.Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2, health_check_interval=30)
        self.client.ping()
        self.prefix = prefix
    def _serializer(self, app): return URLSafeSerializer(app.secret_key, salt=self.salt)
    def _key(self, sid): return self.prefix + sid
    def open_session(self, app, request):
        signed = request.cookies.get(self.get_cookie_name(app))
        if not signed: return self.session_class(new=True)
        try: sid = self._serializer(app).loads(signed)
        except (BadSignature, TypeError, ValueError): return self.session_class(new=True)
        if not isinstance(sid, str) or len(sid) > 128: return self.session_class(new=True)
        try: raw = self.client.get(self._key(sid))
        except Exception as exc:
            app.logger.error('Redis session read failed; refusing client-side fallback')
            raise RuntimeError('LibraAI shared session store unavailable') from exc
        if not raw: return self.session_class(new=True)
        try: data = json.loads(raw)
        except (ValueError, TypeError):
            self.client.delete(self._key(sid)); return self.session_class(new=True)
        if not isinstance(data, dict):
            self.client.delete(self._key(sid)); return self.session_class(new=True)
        return self.session_class(data, sid=sid, new=False)
    def save_session(self, app, session, response):
        name = self.get_cookie_name(app); domain = self.get_cookie_domain(app); path = self.get_cookie_path(app)
        secure = self.get_cookie_secure(app); httponly = self.get_cookie_httponly(app); samesite = self.get_cookie_samesite(app)
        if not session:
            if session.modified and getattr(session, 'sid', None):
                self.client.delete(self._key(session.sid))
                response.delete_cookie(name, domain=domain, path=path, secure=secure, httponly=httponly, samesite=samesite)
            return
        if session.regenerate or session.new:
            old = session.sid; session.sid = secrets.token_urlsafe(32); session.new = False; session.regenerate = False
            if old: self.client.delete(self._key(old))
        ttl = max(1, int(app.permanent_session_lifetime.total_seconds()))
        try: payload = json.dumps(dict(session), separators=(',', ':'), ensure_ascii=False)
        except (TypeError, ValueError) as exc: raise RuntimeError('Session contains non-serializable values') from exc
        try: self.client.set(self._key(session.sid), payload, ex=ttl)
        except Exception as exc:
            app.logger.error('Redis session write failed; refusing client-side fallback')
            raise RuntimeError('LibraAI shared session store unavailable') from exc
        signed = self._serializer(app).dumps(session.sid)
        expires = self.get_expiration_time(app, session) if session.permanent else None
        response.set_cookie(name, signed, expires=expires, httponly=httponly, secure=secure, samesite=samesite, domain=domain, path=path)
