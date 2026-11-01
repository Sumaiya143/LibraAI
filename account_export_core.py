import sqlite3
from datetime import datetime, timezone

USER_TABLES = ('progress', 'annotations', 'reviews', 'wishlist', 'cart', 'loans', 'orders', 'posts', 'flashcards', 'resale', 'audit')


def export_account_data(connection, user_id):
    """Read only the requesting user's records; never expose password hashes."""
    user = connection.execute('SELECT id,name,email,role,plan FROM users WHERE id=?', (user_id,)).fetchone()
    if user is None:
        raise LookupError('Account does not exist')
    result = {'exported_at': datetime.now(timezone.utc).isoformat(),
              'account': dict(zip(('id','name','email','role','plan'), user)), 'records': {}}
    for table in USER_TABLES:
        # Legacy deployments can omit optional modules/tables.
        exists = connection.execute('SELECT 1 FROM sqlite_master WHERE type=\'table\' AND name=?', (table,)).fetchone()
        if not exists:
            continue
        columns = [col[1] for col in connection.execute(f'PRAGMA table_info({table})')]
        if 'user_id' not in columns:
            continue
        rows = connection.execute(f'SELECT * FROM {table} WHERE user_id=?', (user_id,)).fetchall()
        result['records'][table] = [dict(zip(columns, row)) for row in rows]
    return result


