"""Validate referrer-based redirects without permitting open redirects."""
from urllib.parse import urlsplit


def safe_local_return_url(referrer, host, scheme="http"):
    """Return a same-origin absolute referrer, or '/' when it is not safe.

    Exact netloc matching intentionally rejects userinfo tricks, foreign ports,
    protocol-relative URLs, and redirects to other hosts. This helper is kept
    dependency-free so its security behavior can be tested without Flask.
    """
    if not isinstance(referrer, str) or not referrer or not isinstance(host, str) or not host:
        return "/"
    if any(ord(char) < 32 or ord(char) == 127 for char in referrer) or "\\" in referrer:
        return "/"
    try:
        parsed = urlsplit(referrer)
    except ValueError:
        return "/"
    if parsed.scheme.lower() not in {"http", "https"}:
        return "/"
    if parsed.scheme.lower() != str(scheme).lower():
        return "/"
    if parsed.netloc.lower() != host.lower():
        return "/"
    if not parsed.path.startswith("/") or parsed.path.startswith("//"):
        return "/"
    return parsed.path + (("?" + parsed.query) if parsed.query else "") + (("#" + parsed.fragment) if parsed.fragment else "")
