"""Fail closed when the development HTTP server is launched in production."""
import os

PRODUCTION_VALUES = {'production', 'prod', 'live'}

def is_production(environ=None):
    env = os.environ if environ is None else environ
    return str(env.get('LIBRA_ENV', '')).strip().lower() in PRODUCTION_VALUES

def require_development_server(environ=None):
    if is_production(environ):
        raise RuntimeError(
            'Refusing to run ThreadingHTTPServer with LIBRA_ENV=production. '
            'A reviewed production server, HTTPS termination, real gateway credentials, '
            'and a passed security audit are required before launch.'
        )
    return True
