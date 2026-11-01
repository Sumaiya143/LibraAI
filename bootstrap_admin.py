"""Explicit initial administrator setup; no demo users in production."""
import os, sys, sqlite3, getpass, hashlib, base64, re
from pathlib import Path
def generate_password_hash(password):
    # Werkzeug-compatible PBKDF2 string without importing the web application.
    salt = os.urandom(16).hex()
    rounds = 600000
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), rounds).hex()
    return f'pbkdf2:sha256:{rounds}${salt}${digest}' 

def bootstrap(db_path, name, email, password, username=None):
    if not Path(db_path).is_absolute():
        raise ValueError('Database path must be absolute')
    if len(password) < 12 or len(password) > 128:
        raise ValueError('Password must contain 12–128 characters')
    email = email.strip().lower()
    username = (username or name).strip()
    if '@' not in email or len(email)>254 or not name.strip():
        raise ValueError('Invalid name or email')
    if len(username) < 2 or len(username) > 32 or not re.fullmatch(r'[A-Za-z0-9_.-]+', username):
        raise ValueError('Username must be 2–32 characters using letters, numbers, dot, underscore or hyphen')
    conn=sqlite3.connect(db_path,timeout=15)
    try:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]:
            raise ValueError('Administrator already exists; refusing bootstrap')
        columns = {row[1] for row in conn.execute('PRAGMA table_info(users)')}
        if 'username' in columns:
            conn.execute('INSERT INTO users(name,email,username,password,role,plan) VALUES(?,?,?,?,?,?)',
                         (name.strip(),email,username,generate_password_hash(password),'admin','Institutional'))
        else:
            conn.execute('INSERT INTO users(name,email,password,role,plan) VALUES(?,?,?,?,?)',
                         (name.strip(),email,generate_password_hash(password),'admin','Institutional'))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()

if __name__ == '__main__':
    path=os.environ.get('LIBRAAI_DB_PATH')
    if not path:
        sys.exit('Set LIBRAAI_DB_PATH to an absolute path, and initialize schema first')
    name=input('Administrator name: ').strip()
    username=input('Fixed administrator username: ').strip()
    email=input('Administrator email: ').strip()
    password=getpass.getpass('Administrator password (12+ chars): ')
    confirm=getpass.getpass('Confirm password: ')
    if password != confirm:
        sys.exit('Passwords do not match')
    try:
        bootstrap(path,name,email,password,username)
    except (ValueError,sqlite3.Error) as exc:
        sys.exit(str(exc))
    print('Initial administrator created.')
