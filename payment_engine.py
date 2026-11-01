"""Payment ledger and state machine. Browser callbacks are never proof of payment."""
import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

class PaymentError(ValueError): pass

def now(): return datetime.now(timezone.utc).isoformat()

def cents(value):
    """Convert an exact decimal amount to minor units; reject binary floats/booleans.

    Gateway responses must supply an integer or decimal string, not a float that
    might have been rounded by JSON decoding before validation.
    """
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise PaymentError('Invalid amount')
    if isinstance(value, str):
        if not value or value.strip() != value or len(value) > 32:
            raise PaymentError('Invalid amount')
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n < 0 or n.as_tuple().exponent < -2:
            raise PaymentError('Invalid amount')
        result = int(n * 100)
        if result > 9223372036854775807:
            raise PaymentError('Amount exceeds storage range')
        return result
    except (InvalidOperation, TypeError, ValueError, OverflowError):
        raise PaymentError('Invalid amount')

def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS payment_attempts (
      id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, provider TEXT NOT NULL,
      merchant_ref TEXT NOT NULL UNIQUE, provider_ref TEXT UNIQUE,
      amount_cents INTEGER NOT NULL CHECK(amount_cents>0), currency TEXT NOT NULL DEFAULT 'BDT',
      state TEXT NOT NULL DEFAULT 'created', gateway_url TEXT, created TEXT NOT NULL, updated TEXT NOT NULL,
      FOREIGN KEY(order_id) REFERENCES orders(id))''')
    conn.execute('''CREATE UNIQUE INDEX IF NOT EXISTS one_paid_payment_per_order
       ON payment_attempts(order_id) WHERE state='paid' ''')
    conn.execute('''CREATE INDEX IF NOT EXISTS payment_attempts_state_created ON payment_attempts(state,created)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS payment_events (
      id INTEGER PRIMARY KEY, attempt_id INTEGER NOT NULL, event TEXT NOT NULL,
      detail TEXT NOT NULL, created TEXT NOT NULL, FOREIGN KEY(attempt_id) REFERENCES payment_attempts(id))''')
    conn.commit()

def payable_order_cents(conn, order_id, legacy_total):
    """Prefer the exact checkout ledger; refuse inconsistent legacy totals.

    Legacy orders without a ledger entry remain supported for migration.
    """
    amount = cents(str(legacy_total))
    has_table = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='order_amounts'").fetchone()
    if has_table:
        row = conn.execute('SELECT total_cents,currency FROM order_amounts WHERE order_id=?', (order_id,)).fetchone()
        if row:
            exact, currency = row
            if type(exact) is not int or exact < 0 or currency != 'BDT' or exact != amount:
                raise PaymentError('Order amount ledger mismatch; manual reconciliation required')
            # Newly created orders must reconcile every immutable line allocation
            # before initiating or settling payment. Legacy orders without an
            # allocation column remain supported during migration.
            item_table = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='order_items'").fetchone()
            if item_table and any(col[1] == 'line_total_cents' for col in conn.execute('PRAGMA table_info(order_items)')):
                lines = conn.execute('SELECT line_total_cents FROM order_items WHERE order_id=?', (order_id,)).fetchall()
                if not lines or any(type(line[0]) is not int or line[0] < 0 for line in lines):
                    raise PaymentError('Order line allocation missing; manual reconciliation required')
                if sum(line[0] for line in lines) != exact:
                    raise PaymentError('Order line allocation mismatch; manual reconciliation required')
            return exact
    return amount

def create_attempt(conn, order_id, user_id, provider, merchant_ref):
    if provider not in ('sslcommerz','bkash'): raise PaymentError('Unsupported gateway')
    if not isinstance(merchant_ref, str) or not merchant_ref.strip() or len(merchant_ref) > 255 or merchant_ref != merchant_ref.strip():
        raise PaymentError('Invalid merchant reference')
    conn.execute('BEGIN IMMEDIATE')
    try:
        order=conn.execute('SELECT id,user_id,total,status FROM orders WHERE id=?',(order_id,)).fetchone()
        if not order: raise PaymentError('Order not found')
        if order['user_id']!=user_id: raise PaymentError('Forbidden')
        if order['status'] not in ('Awaiting payment — sandbox only','Awaiting payment'):
            raise PaymentError('Order is not payable')
        amount=payable_order_cents(conn, order_id, order['total'])
        if amount<=0: raise PaymentError('Zero-value orders require separate fulfillment')
        existing=conn.execute("SELECT * FROM payment_attempts WHERE order_id=? AND state IN ('created','pending','paid') ORDER BY id DESC LIMIT 1",(order_id,)).fetchone()
        if existing:
            if existing['provider'] != provider:
                raise PaymentError('Existing payment attempt belongs to another gateway')
            if existing['amount_cents'] != amount:
                raise PaymentError('Order total changed after payment initiation; manual reconciliation required')
            conn.commit()
            return dict(existing),False
        conn.execute('INSERT INTO payment_attempts(order_id,provider,merchant_ref,amount_cents,created,updated) VALUES(?,?,?,?,?,?)', (order_id,provider,merchant_ref,amount,now(),now()))
        result=dict(conn.execute('SELECT * FROM payment_attempts WHERE merchant_ref=?',(merchant_ref,)).fetchone())
        conn.commit()
        return result,True
    except Exception:
        conn.rollback(); raise

def abandon_unlaunched_attempt(conn, order_id, user_id, merchant_ref):
    """Allow gateway switching only before any gateway session was launched.

    Never cancel a pending session locally: it may still settle asynchronously.
    """
    conn.execute('BEGIN IMMEDIATE')
    try:
        order = conn.execute('SELECT user_id,status FROM orders WHERE id=?', (order_id,)).fetchone()
        if not order or order['user_id'] != user_id:
            raise PaymentError('Order not found or forbidden')
        if order['status'] not in ('Awaiting payment — sandbox only', 'Awaiting payment'):
            raise PaymentError('Order is not payable')
        a = conn.execute('SELECT * FROM payment_attempts WHERE order_id=? AND merchant_ref=?',
                         (order_id, merchant_ref)).fetchone()
        if not a:
            raise PaymentError('Attempt not found')
        if a['state'] != 'created' or a['provider_ref'] or a['gateway_url']:
            raise PaymentError('Gateway session already initiated; reconciliation required')
        conn.execute("UPDATE payment_attempts SET state='abandoned',updated=? WHERE id=? AND state='created'",
                     (now(), a['id']))
        conn.execute('INSERT INTO payment_events(attempt_id,event,detail,created) VALUES(?,?,?,?)',
                     (a['id'], 'attempt_abandoned', 'Unlaunched attempt cancelled by order owner', now()))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise

def mark_pending(conn, merchant_ref, provider_ref, gateway_url=None):
    if provider_ref is None or provider_ref == '':
        raise PaymentError('Missing gateway session reference')
    if not isinstance(provider_ref, str) or not provider_ref.strip() or len(provider_ref) > 255:
        raise PaymentError('Invalid gateway session reference')
    if gateway_url is not None and (not isinstance(gateway_url, str) or not gateway_url.strip()):
        raise PaymentError('Invalid gateway URL')
    conn.execute('BEGIN IMMEDIATE')
    try:
        a=conn.execute('SELECT * FROM payment_attempts WHERE merchant_ref=?',(merchant_ref,)).fetchone()
        if not a or a['state'] not in ('created','pending'): raise PaymentError('Attempt not pending')
        order = conn.execute('SELECT status,total FROM orders WHERE id=?', (a['order_id'],)).fetchone()
        if not order or order['status'] not in ('Awaiting payment — sandbox only', 'Awaiting payment'):
            raise PaymentError('Order no longer payable; reconciliation required')
        if payable_order_cents(conn, a['order_id'], order['total']) != a['amount_cents']:
            raise PaymentError('Order total changed; reconciliation required')
        if a['provider_ref'] and provider_ref and a['provider_ref']!=provider_ref: raise PaymentError('Gateway reference mismatch')
        if a['state'] == 'pending' and a['gateway_url'] and gateway_url and a['gateway_url'] != gateway_url:
            raise PaymentError('Gateway session URL mismatch')
        conn.execute("UPDATE payment_attempts SET state='pending',provider_ref=COALESCE(provider_ref,?),gateway_url=COALESCE(gateway_url,?),updated=? WHERE id=?",(provider_ref,gateway_url,now(),a['id']))
        conn.commit()
    except Exception:
        conn.rollback();raise

def settle_verified(conn, merchant_ref, provider, provider_ref, amount_cents, currency, verified, raw_status):
    """Call only after trusted server-to-server gateway verification."""
    if verified is not True: raise PaymentError('Payment not independently verified')
    if not isinstance(provider_ref, str) or not provider_ref.strip() or len(provider_ref) > 255:
        raise PaymentError('Invalid provider transaction reference')
    if type(amount_cents) is not int or amount_cents <= 0:
        raise PaymentError('Invalid verified amount')
    if provider not in ('sslcommerz', 'bkash') or currency != 'BDT':
        raise PaymentError('Invalid payment provider or currency')
    conn.execute('BEGIN IMMEDIATE')
    try:
        a=conn.execute('SELECT * FROM payment_attempts WHERE merchant_ref=?',(merchant_ref,)).fetchone()
        if not a or a['provider']!=provider: raise PaymentError('Attempt/provider mismatch')
        if a['amount_cents']!=amount_cents or currency!='BDT': raise PaymentError('Amount or currency mismatch')
        if a['state']=='paid':
            # A repeated callback is idempotent only for the exact same verified transaction.
            # A different transaction reference must never be silently acknowledged.
            if a['provider_ref'] != provider_ref:
                raise PaymentError('Conflicting transaction reference for paid attempt')
            conn.commit();return False
        if a['provider_ref'] and a['provider_ref']!=provider_ref and provider!='sslcommerz': raise PaymentError('Provider transaction mismatch')
        if a['state'] not in ('created','pending'): raise PaymentError('Payment state cannot settle')
        order=conn.execute('SELECT status,total FROM orders WHERE id=?',(a['order_id'],)).fetchone()
        if order and payable_order_cents(conn, a['order_id'], order['total']) != a['amount_cents']:
            raise PaymentError('Order total changed since payment initiation; manual reconciliation required')
        if not order or order['status'] not in ('Awaiting payment — sandbox only','Awaiting payment'):
            raise PaymentError('Order not payable; manual reconciliation needed')
        conn.execute("UPDATE payment_attempts SET state='paid',provider_ref=?,updated=? WHERE id=?",(provider_ref,now(),a['id']))
        conn.execute("UPDATE orders SET status='Paid — fulfillment pending' WHERE id=?",(a['order_id'],))
        # Grant access atomically with settlement, only for licensed digital titles.
        from digital_entitlements import grant_paid_order
        grant_paid_order(conn, a['order_id'])
        conn.execute('INSERT INTO payment_events(attempt_id,event,detail,created) VALUES(?,?,?,?)',(a['id'],'payment_verified',str(raw_status)[:160],now()))
        conn.commit();return True
    except (sqlite3.IntegrityError, Exception):
        conn.rollback();raise


def pending_for_reconciliation(conn, limit=100):
    """Return unsettled gateway sessions for an external scheduler; never settle by age alone."""
    if type(limit) is not int or not 1 <= limit <= 500:
        raise PaymentError('Invalid batch size')
    return [dict(row) for row in conn.execute(
        "SELECT * FROM payment_attempts WHERE state='pending' AND provider_ref IS NOT NULL ORDER BY created,id LIMIT ?", (limit,))]

def record_reconciliation_event(conn, merchant_ref, event, detail):
    if event not in ('gateway_pending','gateway_rejected','manual_review'):
        raise PaymentError('Invalid reconciliation event')
    conn.execute('BEGIN IMMEDIATE')
    try:
        a=conn.execute('SELECT id FROM payment_attempts WHERE merchant_ref=?',(merchant_ref,)).fetchone()
        if not a: raise PaymentError('Unknown attempt')
        conn.execute('INSERT INTO payment_events(attempt_id,event,detail,created) VALUES(?,?,?,?)',
                     (a['id'],event,str(detail)[:160],now()))
        conn.commit()
    except Exception:
        conn.rollback();raise
