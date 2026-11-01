"""Creator royalty payout ledger. Tracks accounting and manual disbursement evidence; never fakes a gateway transfer."""
from __future__ import annotations
import base64, hashlib, os, re, secrets
from datetime import datetime, timezone

ACTIVE_RESERVATION = ('requested','approved','processing')
ALL_STATES = ('requested','approved','processing','paid','rejected','failed')


def setup(conn):
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS creator_payout_requests (
      id INTEGER PRIMARY KEY AUTOINCREMENT, creator_user_id INTEGER NOT NULL,
      amount_cents INTEGER NOT NULL CHECK(amount_cents > 0), currency TEXT NOT NULL DEFAULT 'BDT',
      method TEXT NOT NULL CHECK(method IN ('bkash','nagad','bank_transfer')),
      destination_ciphertext TEXT NOT NULL, destination_masked TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'requested' CHECK(status IN ('requested','approved','processing','paid','rejected','failed')),
      idempotency_key TEXT NOT NULL, admin_note TEXT, provider_reference TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      reviewed_by INTEGER, paid_at TEXT, UNIQUE(creator_user_id,idempotency_key));
    CREATE INDEX IF NOT EXISTS idx_creator_payout_owner ON creator_payout_requests(creator_user_id,created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_creator_payout_status ON creator_payout_requests(status,created_at);
    CREATE TABLE IF NOT EXISTS creator_payout_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, payout_id INTEGER NOT NULL,
      actor_user_id INTEGER NOT NULL, old_status TEXT, new_status TEXT NOT NULL,
      note TEXT, provider_reference TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(payout_id) REFERENCES creator_payout_requests(id));
    CREATE TABLE IF NOT EXISTS royalty_adjustments (
      id INTEGER PRIMARY KEY AUTOINCREMENT, creator_user_id INTEGER NOT NULL,
      order_item_id INTEGER, amount_cents INTEGER NOT NULL CHECK(amount_cents <> 0),
      reason TEXT NOT NULL, reference TEXT NOT NULL UNIQUE, actor_user_id INTEGER NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    ''')


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError('Install cryptography to enable encrypted payout destinations.') from exc
    secret = os.getenv('SECRET_KEY', '').strip()
    if len(secret) < 32:
        raise RuntimeError('Set a stable SECRET_KEY of at least 32 characters before enabling creator payouts.')
    key = base64.urlsafe_b64encode(hashlib.sha256(('libraai-creator-payout-v1:' + secret).encode()).digest())
    return Fernet(key)


def encrypt_destination(value: str) -> str:
    return _fernet().encrypt(value.encode('utf-8')).decode('ascii')


def decrypt_destination(value: str) -> str:
    return _fernet().decrypt(value.encode('ascii')).decode('utf-8')


def mask_destination(value: str) -> str:
    compact = re.sub(r'\s+', '', value)
    if len(compact) <= 4:
        return '*' * len(compact)
    return '*' * max(4, len(compact)-4) + compact[-4:]


def balance(conn, creator_id: int):
    earned = conn.execute('SELECT COALESCE(SUM(royalty_cents),0) FROM royalty_ledger WHERE creator_user_id=?',(creator_id,)).fetchone()[0]
    adjustments = conn.execute('SELECT COALESCE(SUM(amount_cents),0) FROM royalty_adjustments WHERE creator_user_id=?',(creator_id,)).fetchone()[0]
    paid = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM creator_payout_requests WHERE creator_user_id=? AND status='paid'",(creator_id,)).fetchone()[0]
    reserved = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM creator_payout_requests WHERE creator_user_id=? AND status IN ('requested','approved','processing')",(creator_id,)).fetchone()[0]
    total = int(earned or 0) + int(adjustments or 0)
    return {'earned_cents':int(earned or 0),'adjustments_cents':int(adjustments or 0),'paid_cents':int(paid or 0),'reserved_cents':int(reserved or 0),'available_cents':max(0,total-int(paid or 0)-int(reserved or 0)),'net_earned_cents':total}


def request_payout(conn, creator_id: int, amount_cents: int, method: str, destination: str, idempotency_key: str):
    if type(amount_cents) is not int or amount_cents < 100:
        raise ValueError('Minimum payout request is ৳1.00 (100 paisa).')
    if method not in ('bkash','nagad','bank_transfer'):
        raise ValueError('Choose bKash, Nagad or bank transfer.')
    destination = destination.strip()
    if not 5 <= len(destination) <= 180 or any(ord(ch) < 32 for ch in destination):
        raise ValueError('Payout destination is invalid.')
    if method in ('bkash','nagad'):
        normalized_phone = re.sub(r'[\s-]+', '', destination)
        if not re.fullmatch(r'(?:\+?8801|01)[3-9]\d{8}', normalized_phone):
            raise ValueError('Enter a valid Bangladesh mobile-wallet number (01XXXXXXXXX or +8801XXXXXXXXX).')
    if not re.fullmatch(r'[A-Za-z0-9._:-]{12,100}', idempotency_key or ''):
        raise ValueError('A valid idempotency key is required.')
    existing = conn.execute('SELECT id FROM creator_payout_requests WHERE creator_user_id=? AND idempotency_key=?',(creator_id,idempotency_key)).fetchone()
    if existing:
        return int(existing[0]), False
    available = balance(conn,creator_id)['available_cents']
    if amount_cents > available:
        raise ValueError(f'Insufficient available balance. Available: {available} cents.')
    cipher = encrypt_destination(destination)
    cur = conn.execute('''INSERT INTO creator_payout_requests
      (creator_user_id,amount_cents,method,destination_ciphertext,destination_masked,idempotency_key)
      VALUES(?,?, ?,?,?,?)''',(creator_id,amount_cents,method,cipher,mask_destination(destination),idempotency_key))
    pid = int(cur.lastrowid)
    conn.execute('INSERT INTO creator_payout_events(payout_id,actor_user_id,old_status,new_status,note) VALUES(?,?,NULL,?,?)',(pid,creator_id,'requested','Creator submitted payout request'))
    return pid, True


def transition(conn, payout_id: int, actor_id: int, new_status: str, note: str = '', reference: str = ''):
    if new_status not in ALL_STATES:
        raise ValueError('Invalid payout status.')
    note = (note or '').strip()[:500]
    reference = (reference or '').strip()[:180]
    row = conn.execute('SELECT * FROM creator_payout_requests WHERE id=?',(payout_id,)).fetchone()
    if not row: raise LookupError('Payout request not found.')
    old = row['status']
    allowed = {'requested':{'approved','rejected'},'approved':{'processing','paid','failed','rejected'},'processing':{'paid','failed'},'failed':{'processing'},'paid':set(),'rejected':set()}
    if new_status == old: return False
    if new_status not in allowed.get(old,set()):
        raise ValueError(f'Cannot transition payout from {old} to {new_status}.')
    if new_status == 'paid' and not reference:
        raise ValueError('A real bank/provider transaction reference is required before marking paid.')
    if reference:
        duplicate = conn.execute("SELECT 1 FROM creator_payout_requests WHERE provider_reference=? AND id<>? AND status='paid'",(reference,payout_id)).fetchone()
        if duplicate: raise ValueError('This transaction reference is already used by another paid payout.')
    paid_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S') if new_status == 'paid' else row['paid_at']
    conn.execute('''UPDATE creator_payout_requests SET status=?,admin_note=?,provider_reference=?,reviewed_by=?,paid_at=?,updated_at=CURRENT_TIMESTAMP WHERE id=?''',
                 (new_status,note or row['admin_note'],reference or row['provider_reference'],actor_id,paid_at,payout_id))
    conn.execute('''INSERT INTO creator_payout_events(payout_id,actor_user_id,old_status,new_status,note,provider_reference)
                    VALUES(?,?,?,?,?,?)''',(payout_id,actor_id,old,new_status,note,reference or None))
    return True


def list_requests(conn, creator_id=None, limit=200):
    if creator_id is None:
        rows=conn.execute('''SELECT p.*,u.name AS creator_name,u.email AS creator_email FROM creator_payout_requests p JOIN users u ON u.id=p.creator_user_id ORDER BY CASE p.status WHEN 'requested' THEN 0 WHEN 'approved' THEN 1 WHEN 'processing' THEN 2 ELSE 3 END,p.id DESC LIMIT ?''',(limit,)).fetchall()
    else:
        rows=conn.execute('SELECT * FROM creator_payout_requests WHERE creator_user_id=? ORDER BY id DESC LIMIT ?',(creator_id,limit)).fetchall()
    return [dict(r) for r in rows]
