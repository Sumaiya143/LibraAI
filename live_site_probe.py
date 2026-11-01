"""Read-only production smoke probe; never submits orders or payments."""
import argparse
import json
import ssl
import sys
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError


class NoRedirects(HTTPRedirectHandler):
    """Never follow redirects when probing a production origin."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def secure_opener(req):
    client = build_opener(NoRedirects(), HTTPSHandler(context=ssl.create_default_context()))
    return client.open(req, timeout=12)


def probe(origin, opener=None):
    """Return structured checks without printing secrets or contacting payment providers."""
    from commercial_readiness import valid_public_origin
    results = []
    if not valid_public_origin(origin):
        return {'passed': False, 'checks': [{'name': 'public_https_origin', 'ok': False, 'detail': 'HTTPS DNS origin required'}]}
    results.append({'name': 'public_https_origin', 'ok': True})
    opener = opener or secure_opener
    for path in ('/api/health', '/api/ready'):
        try:
            req_url = origin + path
            with opener(Request(req_url, headers={'User-Agent': 'LibraAI-ReadOnly-Launch-Probe/1.0'})) as response:
                status = response.status
                final_url = response.geturl() if hasattr(response, 'geturl') else req_url
                headers = response.headers
                payload = response.read(65537)
                ok = status == 200 and len(payload) <= 65536 and final_url == req_url
                results.append({'name': path + '_http', 'ok': ok, 'status': status})
                if path == '/api/ready':
                    try:
                        body = json.loads(payload)
                        ready = body.get('status') == 'ready' and body.get('scope') == 'database-and-application-only'
                    except (ValueError, AttributeError):
                        ready = False
                    results.append({'name': 'app_database_readiness', 'ok': ready, 'detail': 'Not a payment or licensing verification'})
                for header in ('X-Content-Type-Options', 'Content-Security-Policy', 'Strict-Transport-Security'):
                    results.append({'name': path + '_' + header, 'ok': bool(headers.get(header))})
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            results.append({'name': path + '_http', 'ok': False, 'detail': type(exc).__name__})
    return {'passed': all(item['ok'] for item in results), 'checks': results,
            'limitations': ['No payment/refund transaction executed', 'No licensed-content rights verified', 'No independent security audit performed']}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only LibraAI HTTPS smoke probe')
    parser.add_argument('origin', help='Public HTTPS origin, e.g. https://books.example.com')
    args = parser.parse_args(argv)
    result = probe(args.origin)
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
