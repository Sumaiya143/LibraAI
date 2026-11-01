"""Atomic credential rotation, independent of Flask for isolated testing."""
import sqlite3

class PasswordChangeError(ValueError):
    pass

def change_password(conn, user_id, old_password, new_password, verify, hash_password):
    if not isinstance(user_id, int) or user_id < 1:
        raise PasswordChangeError('Authentication required.')
    if not isinstance(old_password, str) or not isinstance(new_password, str):
        raise PasswordChangeError('Invalid password input.')
    if not 12 <= len(new_password) <= 128:
        raise PasswordChangeError('New password must be 12–128 characters.')
    if old_password == new_password:
        raise PasswordChangeError('Choose a different password.')
    row = conn.execute('SELECT password FROM users WHERE id=?', (user_id,)).fetchone()
    if row is None or not verify(row[0], old_password):
        raise PasswordChangeError('Current password is incorrect.')
    new_hash = hash_password(new_password)
    # Compare-and-swap avoids silently overwriting a concurrent credential update.
    cur = conn.execute('UPDATE users SET password=? WHERE id=? AND password=?',
                       (new_hash, user_id, row[0]))
    if cur.rowcount != 1:
        conn.rollback()
        raise PasswordChangeError('Account changed during this request. Please retry.')
    conn.commit()
    return True
