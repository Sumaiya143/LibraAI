"""Authenticated, read-only fulfillment dashboard integration for LibraAI."""
import sqlite3
from mixed_fulfillment_audit import inspect_order


def dashboard_data(conn, limit=50, offset=0, exceptions_only=False):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('limit must be between 1 and 100')
    if type(offset) is not int or not 0 <= offset <= 1000000:
        raise ValueError('invalid offset')
    if type(exceptions_only) is not bool:
        raise ValueError('invalid exceptions_only')
    # Audit only the requested page; avoid loading entire order history.
    ids = [row[0] for row in conn.execute(
        'SELECT id FROM orders ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()]
    results = [inspect_order(conn, order_id) for order_id in ids]
    if exceptions_only:
        results = [result for result in results if not result['ready']]
    # Deliberately omit address, customer ID and any gateway credentials.
    return [{'order_id': result['order_id'], 'status': result['status'],
             'ready': result['ready'], 'issues': result['issues'],
             'print_line_count': result['print_line_count'],
             'digital_line_count': result['digital_line_count']}
            for result in results]


def dashboard_page(conn, limit=50, offset=0, exceptions_only=False):
    """Return bounded rows and honest pagination metadata.

    Exceptions filtering is scoped to the current unfiltered page, never the
    entire history. A one-row lookahead avoids a misleading Next link.
    """
    rows = dashboard_data(conn, limit, offset, exceptions_only)
    has_next = conn.execute('SELECT 1 FROM orders ORDER BY id DESC LIMIT 1 OFFSET ?',
                            (offset + limit,)).fetchone() is not None
    return {'rows': rows, 'has_next': has_next, 'has_previous': offset > 0,
            'limit': limit, 'offset': offset, 'exceptions_only': exceptions_only}
