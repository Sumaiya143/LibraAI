"""Signed-cookie session lifetime helpers for LibraAI authentication."""
import time

IDLE_TIMEOUT_SECONDS = 30 * 60
ABSOLUTE_TIMEOUT_SECONDS = 12 * 60 * 60


def start_authenticated_session(session_data, now=None):
    """Stamp a newly authenticated session after clearing any prior identity."""
    now = int(time.time() if now is None else now)
    session_data['_auth_started_at'] = now
    session_data['_auth_last_seen_at'] = now


def session_expired(session_data, now=None,
                    idle_timeout=IDLE_TIMEOUT_SECONDS,
                    absolute_timeout=ABSOLUTE_TIMEOUT_SECONDS):
    """Fail closed for legacy sessions without timestamps and expired sessions."""
    now = int(time.time() if now is None else now)
    started = session_data.get('_auth_started_at')
    last_seen = session_data.get('_auth_last_seen_at')
    if not isinstance(started, int) or not isinstance(last_seen, int):
        return True
    if started > now or last_seen > now:
        return True
    return (now - started >= absolute_timeout or
            now - last_seen >= idle_timeout)


def touch_authenticated_session(session_data, now=None):
    """Update the last-activity timestamp for a valid authenticated session."""
    session_data['_auth_last_seen_at'] = int(time.time() if now is None else now)
