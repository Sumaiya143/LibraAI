"""Small single-process API abuse guard and privacy-safe request telemetry.

This limiter is intentionally a single-host fallback. Multi-worker/multi-host
production deployments must use a shared atomic store (Redis or equivalent).
"""
from __future__ import annotations
import hashlib
import hmac
import os
import json
import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Callable

_LOCK = threading.Lock()
_REDIS_CLIENT_LOCK = threading.Lock()
_REDIS_CLIENT = None
_REDIS_CLIENT_URL = None
_FINGERPRINT_SALT = (os.getenv('LIBRAAI_RATE_LIMIT_HMAC_KEY') or os.getenv('SECRET_KEY') or secrets.token_hex(32)).encode('utf-8')
_EVENTS: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_RULES = (
    ("/login", 10, 60),
    ("/signup", 8, 60),
    ("/forgot-password", 5, 300),
    ("/api/ai", 20, 60),
    ("/api/creator/royalty-payouts", 5, 60),
    ("/api/payments/start", 8, 60),
)


def _shared_redis_client(redis_url: str):
    """Reuse one bounded-timeout Redis connection pool per worker."""
    global _REDIS_CLIENT, _REDIS_CLIENT_URL
    if _REDIS_CLIENT is not None and _REDIS_CLIENT_URL == redis_url:
        return _REDIS_CLIENT
    with _REDIS_CLIENT_LOCK:
        if _REDIS_CLIENT is not None and _REDIS_CLIENT_URL == redis_url:
            return _REDIS_CLIENT
        import redis
        _REDIS_CLIENT = redis.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2,
                                             decode_responses=True, health_check_interval=30)
        _REDIS_CLIENT_URL = redis_url
        return _REDIS_CLIENT


def client_fingerprint(remote_addr: str | None) -> str:
    """Return a stable, non-reversible identifier for short-lived rate keys."""
    raw = (remote_addr or "unknown").encode("utf-8", "replace")
    return hmac.new(_FINGERPRINT_SALT, raw, hashlib.sha256).hexdigest()[:24]


def rule_for(path: str, method: str):
    if method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    for prefix, limit, window in _RULES:
        if path == prefix or path.startswith(prefix + "/"):
            return prefix, limit, window
    return None


def check_rate_limit(path: str, method: str, remote_addr: str | None,
                     now: float | None = None) -> dict | None:
    """Return a safe 429 descriptor when over limit, else None."""
    rule = rule_for(path, method)
    if rule is None:
        return None
    prefix, limit, window = rule
    now = time.time() if now is None else float(now)
    fingerprint = client_fingerprint(remote_addr)
    backend = os.getenv('LIBRAAI_RATE_LIMIT_BACKEND', 'memory').strip().lower()
    if backend == 'redis':
        redis_url = os.getenv('REDIS_URL', '').strip()
        if not redis_url:
            return {"status": 503, "error": "rate_limit_backend_unavailable", "message": "Shared rate-limit storage is not configured."}
        try:
            import redis
            client = redis.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2, decode_responses=True)
            # Atomic fixed-window counter shared by all workers. Expiry is created
            # only on the first increment to avoid extending the window per request.
            script = """local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; local ttl=redis.call('TTL',KEYS[1]); return {n,ttl}"""
            count, ttl = client.eval(script, 1, 'libraai:ratelimit:'+prefix+':'+fingerprint, window)
            if int(count) > limit:
                return {"error":"rate_limit_exceeded", "message":"Too many requests. Please wait and try again.", "retry_after":max(1,int(ttl)), "status":429}
            return None
        except Exception:
            # Fail closed for abuse-sensitive endpoints rather than bypassing a
            # configured shared limiter when Redis is unhealthy.
            return {"status":503, "error":"rate_limit_backend_unavailable", "message":"Request protection is temporarily unavailable. Please retry shortly."}
    if backend != 'memory':
        return {"status":503, "error":"rate_limit_backend_invalid", "message":"Rate-limit backend configuration is invalid."}
    key = (prefix, fingerprint)
    with _LOCK:
        events = _EVENTS[key]
        while events and events[0] <= now - window:
            events.popleft()
        if len(events) >= limit:
            retry_after = max(1, int(window - (now - events[0])))
            return {"error": "rate_limit_exceeded", "message": "Too many requests. Please wait and try again.", "retry_after": retry_after}
        events.append(now)
        # Opportunistic cleanup bounds memory in long-lived workers.
        if len(_EVENTS) > 5000:
            expired_before = now - max(rule[2] for rule in _RULES)
            for old_key in list(_EVENTS.keys())[:1000]:
                if not _EVENTS[old_key] or _EVENTS[old_key][-1] <= expired_before:
                    _EVENTS.pop(old_key, None)
    return None


def reset_rate_limits_for_tests() -> None:
    global _REDIS_CLIENT, _REDIS_CLIENT_URL
    with _LOCK:
        _EVENTS.clear()
    with _REDIS_CLIENT_LOCK:
        _REDIS_CLIENT = None
        _REDIS_CLIENT_URL = None


class JsonRequestFormatter(__import__('logging').Formatter):
    """JSON formatter for request telemetry; serializes only explicit safe fields."""
    def format(self, record):
        payload = {
            'timestamp': self.formatTime(record, '%Y-%m-%dT%H:%M:%S'),
            'event': getattr(record, 'event_name', 'request_event'),
            'request_id': getattr(record, 'request_id', None),
            'method': getattr(record, 'method', None),
            'route': getattr(record, 'route', None),
            'status': getattr(record, 'status', None),
            'duration_ms': getattr(record, 'duration_ms', None),
            'client_fingerprint': getattr(record, 'client_fingerprint', None),
        }
        return json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
