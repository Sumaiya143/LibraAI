"""Dependency-free policy checks for content licensing metadata."""
from datetime import datetime, timezone


def license_is_active(document, now=None, territory=None):
    """Fail closed for revoked, suspended, future, expired, or malformed rights."""
    now = now or datetime.now(timezone.utc)
    if isinstance(now, str):
        try: now = datetime.fromisoformat(now.replace('Z', '+00:00'))
        except ValueError: return False
    if now.tzinfo is None: now = now.replace(tzinfo=timezone.utc)
    def get(key, default=None):
        try: return document.get(key, default)
        except AttributeError: return document[key] if key in document else default
    if str(get('license_status', 'active')).lower() != 'active':
        return False
    def parse_date(value):
        if not value: return None
        try:
            parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except (ValueError, TypeError): return False
    valid_from = parse_date(get('license_valid_from'))
    expires = parse_date(get('license_expires_at'))
    if valid_from is False or expires is False: return False
    if valid_from and now < valid_from: return False
    if expires and now >= expires: return False
    territories = str(get('license_territories', '*') or '*')
    allowed = {x.strip().upper() for x in territories.split(',') if x.strip()}
    if '*' not in allowed and (not territory or territory.upper() not in allowed): return False
    return True


def license_allows_format(document, requested_format):
    """Return whether the recorded grant covers the requested distribution format."""
    try: value = document.get('licensed_formats', 'ebook')
    except AttributeError: value = document['licensed_formats'] if 'licensed_formats' in document else 'ebook'
    allowed = {part.strip().lower() for part in str(value or 'ebook').split(',') if part.strip()}
    requested = str(requested_format or '').strip().lower()
    return requested in allowed or '*' in allowed
