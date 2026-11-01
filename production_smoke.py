"""Non-destructive, fail-closed HTTP smoke checks for a deployed LibraAI instance.

Run: python production_smoke.py https://your-domain.example
No payment is created and no state-changing request is made. This is not a security audit.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

MAX_SMOKE_BODY_BYTES = 100_000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Do not silently follow redirects during an origin/security check."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check(base, path):
    req = urllib.request.Request(
        base + path,
        headers={'Accept': 'application/json', 'User-Agent': 'LibraAI-Deployment-Smoke/1.1'},
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        response = opener.open(req, timeout=12)
    except urllib.error.HTTPError as exc:
        # Preserve the status for a useful failure report; redirects are not followed.
        response = exc
    with response:
        body = response.read(MAX_SMOKE_BODY_BYTES + 1)
        if len(body) > MAX_SMOKE_BODY_BYTES:
            raise ValueError('response body exceeds smoke-check size limit')
        return response.status, dict(response.headers.items()), body


def run(base):
    url = urllib.parse.urlsplit(base)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.path not in ('', '/')):
        raise ValueError('Supply a clean HTTPS origin, e.g. https://books.example.com')
    base = base.rstrip('/')
    failures = []
    endpoints = [('/api/health', 'alive'), ('/api/ready', 'ready')]
    required_headers = {
        'x-content-type-options': 'nosniff',
        'x-frame-options': 'DENY',
        'content-security-policy': None,
        'referrer-policy': 'strict-origin-when-cross-origin',
        'permissions-policy': None,
        'strict-transport-security': None,
        'cache-control': None,
    }
    for path, expected_status in endpoints:
        try:
            status, headers, body = check(base, path)
            header_map = {k.lower(): v for k, v in headers.items()}
            payload = json.loads(body)
            ok = status == 200 and isinstance(payload, dict) and payload.get('status') == expected_status
            print(f'{path}: HTTP {status}, status={payload.get("status") if isinstance(payload, dict) else "invalid"!r}: {"PASS" if ok else "FAIL"}')
            if not ok:
                failures.append(path)
            content_type = header_map.get('content-type', '').lower()
            ct_ok = 'application/json' in content_type
            print(f'{path} content-type JSON: {"PASS" if ct_ok else "FAIL"}')
            if not ct_ok:
                failures.append(path + ':content-type')
            for name, expected in required_headers.items():
                value = header_map.get(name, '')
                present = bool(value)
                if expected is not None:
                    present = value.lower() == expected.lower()
                if name == 'content-security-policy':
                    present = "frame-ancestors 'none'" in value and "object-src 'none'" in value
                elif name == 'permissions-policy':
                    present = all(directive in value for directive in ('camera=()', 'microphone=()', 'geolocation=()'))
                elif name == 'strict-transport-security':
                    present = 'max-age=' in value.lower() and 'includeSubDomains'.lower() in value.lower()
                elif name == 'cache-control':
                    present = 'no-store' in value.lower()
                print(f'{path} header {name}: {"PASS" if present else "FAIL"}')
                if not present:
                    failures.append(path + ':header:' + name)
        except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
            # Report the error class, not URLs, bodies, or possibly sensitive response details.
            print(f'{path}: FAIL ({type(exc).__name__})')
            failures.append(path)
    print('NOTE: This checks public health/readiness endpoints and basic HTTP headers only; it does not verify payments, refunds, licensing, access control, or security certification.')
    return 1 if failures else 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python production_smoke.py https://your-domain.example', file=sys.stderr)
        sys.exit(2)
    try:
        sys.exit(run(sys.argv[1]))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
