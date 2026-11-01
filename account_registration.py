"""Validated account creation shared by public signup and admin user management."""
import re
import sqlite3


class AccountRegistrationError(ValueError):
    """Safe, user-facing account validation error."""


PUBLIC_ACCOUNT_TYPES = {
    'customer': ('reader', 'Free'),
    'merchant': ('creator', 'Creator'),
    'seller': ('creator', 'Creator'),
}
MANAGED_ACCOUNT_TYPES = {
    **PUBLIC_ACCOUNT_TYPES,
    'admin': ('admin', 'Institutional'),
    'librarian': ('librarian', 'Institutional'),
}


def validate_account(name, email, password):
    """Return normalized identity fields or raise a safe validation error."""
    if not isinstance(name, str) or not isinstance(email, str):
        raise AccountRegistrationError('Enter your name and a valid email address.')
    name = name.strip()
    email = email.strip().lower()
    if not isinstance(password, str):
        raise AccountRegistrationError('Invalid password.')
    if not 2 <= len(name) <= 100:
        raise AccountRegistrationError('Name must contain 2–100 characters.')
    if len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise AccountRegistrationError('Enter a valid email address.')
    if not 12 <= len(password) <= 128:
        raise AccountRegistrationError('Password must contain 12–128 characters.')
    return name, email, password


def create_account(conn, name, email, password, role, plan, hash_password, merchant_name=None, username=None):
    """Insert one account; the UNIQUE email constraint remains the race-safe guard."""
    name, email, password = validate_account(name, email, password)
    if role not in {'reader', 'creator', 'admin', 'librarian'}:
        raise AccountRegistrationError('Unsupported account role.')
    if merchant_name is not None:
        if not isinstance(merchant_name, str):
            raise AccountRegistrationError('Store name must be text.')
        merchant_name = merchant_name.strip()
        if merchant_name == '':
            merchant_name = None
        elif not 2 <= len(merchant_name) <= 120:
            raise AccountRegistrationError('Store name must contain 2–120 characters.')
    password_hash = hash_password(password)
    supplied_username = bool(username and str(username).strip())
    if supplied_username:
        username = str(username).strip()
    else:
        username = re.sub(r'[^A-Za-z0-9_.-]+', '.', name).strip('.').lower()[:24]
        if len(username) < 2:
            local_part = email.split('@', 1)[0]
            username = re.sub(r'[^A-Za-z0-9_.-]+', '.', local_part).strip('.').lower()[:24] or 'reader'
    if not 2 <= len(username) <= 32 or not re.fullmatch(r'[A-Za-z0-9_.-]+', username):
        raise AccountRegistrationError('Username must be 2–32 characters and use letters, numbers, dots, underscores or hyphens.')
    try:
        if conn.execute('SELECT 1 FROM users WHERE lower(email)=lower(?)', (email,)).fetchone():
            raise AccountRegistrationError('This email is already registered. Sign in or use another email.')
        columns = {row[1] for row in conn.execute('PRAGMA table_info(users)').fetchall()}
        if 'username' in columns:
            if conn.execute('SELECT 1 FROM users WHERE lower(username)=lower(?)', (username,)).fetchone():
                if supplied_username:
                    raise AccountRegistrationError('This username is already taken. Choose another one.')
                base = username[:24] or 'reader'
                suffix = 2
                while conn.execute('SELECT 1 FROM users WHERE lower(username)=lower(?)', (f'{base}{suffix}',)).fetchone():
                    suffix += 1
                username = f'{base}{suffix}'
            cursor = conn.execute(
                'INSERT INTO users(name,username,email,password,role,plan) VALUES(?,?,?,?,?,?)',
                (name, username, email, password_hash, role, plan),
            )
        else:
            cursor = conn.execute(
                'INSERT INTO users(name,email,password,role,plan) VALUES(?,?,?,?,?)',
                (name, email, password_hash, role, plan),
            )
        if role == 'creator':
            conn.execute(
                'INSERT INTO merchant_profiles(user_id,store_name) VALUES(?,?)',
                (cursor.lastrowid, merchant_name or name),
            )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise
    return cursor.lastrowid, password_hash
