"""Refund accounting state machine. Never claims a refund occurred without verified provider evidence.

This is a ledger/workflow, NOT a gateway refund API integration.
"""
import sqlite3
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

class RefundError(ValueError): pass

def timestamp(): return datetime.now(timezone.utc).isoformat()

def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS refund_requests (
        id INTEGER PRIMARY KEY, attempt_id INTEGER NOT NULL REFERENCES payment_attempts(id),
        order_id INTEGER NOT NULL REFERENCES orders(id), amount_cents INTEGER NOT NULL CHECK(amount_cents>0),
        reason TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('requested','approved','rejected','refunded')),
        provider_ref TEXT UNIQUE, created TEXT NOT NULL, updated TEXT NOT NULL)''')
    conn.execute('CREATE INDEX IF NOT EXISTS refund_by_order ON refund_requests(order_id,state)')
    conn.execute('''CREATE TABLE IF NOT EXISTS refund_item_allocations (
        refund_id INTEGER PRIMARY KEY REFERENCES refund_requests(id),
        order_item_id INTEGER NOT NULL REFERENCES order_items(id),
        amount_cents INTEGER NOT NULL CHECK(amount_cents > 0))''')
    conn.execute('CREATE INDEX IF NOT EXISTS refund_allocations_by_item ON refund_item_allocations(order_item_id)')
    conn.execute('''CREATE TABLE IF NOT EXISTS refund_events (
        id INTEGER PRIMARY KEY, refund_id INTEGER NOT NULL REFERENCES refund_requests(id),
        actor_id INTEGER, event TEXT NOT NULL, created TEXT NOT NULL)''')
    conn.commit()

def request_refund(conn, order_id, actor_id, amount_cents, reason, admin=False, item_id=None):
    if type(order_id) is not int or order_id<=0 or type(actor_id) is not int or actor_id<=0: raise RefundError('Invalid order or actor')
    if type(amount_cents) is not int or amount_cents<=0: raise RefundError('Invalid refund amount')
    if item_id is not None and (type(item_id) is not int or item_id<=0): raise RefundError('Invalid order item')
    if not isinstance(reason,str) or not 5<=len(reason.strip())<=500: raise RefundError('Reason must be 5–500 characters')
    conn.execute('BEGIN IMMEDIATE')
    try:
        order=conn.execute('SELECT user_id,status FROM orders WHERE id=?',(order_id,)).fetchone()
        if not order: raise RefundError('Order not found')
        if order['user_id']!=actor_id and not admin: raise RefundError('Forbidden')
        attempts=conn.execute("SELECT id,amount_cents FROM payment_attempts WHERE order_id=? AND state='paid'",(order_id,)).fetchall()
        if not attempts: raise RefundError('No verified payment to refund')
        if len(attempts)!=1: raise RefundError('Multiple paid attempts require manual reconciliation')
        attempt=attempts[0]
        allocated=conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM refund_requests WHERE attempt_id=? AND state!='rejected'",(attempt['id'],)).fetchone()[0]
        if amount_cents>attempt['amount_cents']-allocated: raise RefundError('Refund exceeds remaining paid balance')
        if item_id is not None:
            has_line_total=any(r[1]=='line_total_cents' for r in conn.execute('PRAGMA table_info(order_items)'))
            fields='unit_price_cents,quantity,line_total_cents' if has_line_total else 'unit_price_cents,quantity'
            item=conn.execute(f'SELECT {fields} FROM order_items WHERE id=? AND order_id=?',(item_id,order_id)).fetchone()
            if not item: raise RefundError('Order item not found')
            line_cap=item['line_total_cents'] if has_line_total and item['line_total_cents'] is not None else item['unit_price_cents']*item['quantity']
            if line_cap<=0: raise RefundError('Invalid item price snapshot')
            reserved=conn.execute('''SELECT COALESCE(SUM(a.amount_cents),0)
                FROM refund_item_allocations a JOIN refund_requests r ON r.id=a.refund_id
                WHERE a.order_item_id=? AND r.state!='rejected' ''',(item_id,)).fetchone()[0]
            if amount_cents>line_cap-reserved: raise RefundError('Refund exceeds remaining item balance')
        cur=conn.execute('INSERT INTO refund_requests(attempt_id,order_id,amount_cents,reason,state,created,updated) VALUES(?,?,?,?,?,?,?)',
            (attempt['id'],order_id,amount_cents,reason.strip(),'requested',timestamp(),timestamp()))
        rid=cur.lastrowid
        if item_id is not None:
            conn.execute('INSERT INTO refund_item_allocations(refund_id,order_item_id,amount_cents) VALUES(?,?,?)',(rid,item_id,amount_cents))
        conn.execute('INSERT INTO refund_events(refund_id,actor_id,event,created) VALUES(?,?,?,?)',(rid,actor_id,'requested',timestamp()))
        conn.commit();return rid
    except Exception:
        conn.rollback();raise

def review_refund(conn, refund_id, actor_id, approve, admin=False):
    if not admin: raise RefundError('Admin authorization required')
    conn.execute('BEGIN IMMEDIATE')
    try:
        row=conn.execute('SELECT state FROM refund_requests WHERE id=?',(refund_id,)).fetchone()
        if not row or row['state']!='requested': raise RefundError('Refund not awaiting review')
        state='approved' if approve else 'rejected'
        conn.execute('UPDATE refund_requests SET state=?,updated=? WHERE id=?',(state,timestamp(),refund_id))
        conn.execute('INSERT INTO refund_events(refund_id,actor_id,event,created) VALUES(?,?,?,?)',(refund_id,actor_id,state,timestamp()))
        conn.commit()
    except Exception:
        conn.rollback();raise

def confirm_provider_refund(conn, refund_id, provider_ref, verified=False):
    """Call only after independent gateway query proves actual refund, not a browser callback."""
    if verified is not True: raise RefundError('Gateway confirmation required')
    if not isinstance(provider_ref,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{2,159}',provider_ref,flags=re.ASCII): raise RefundError('Invalid provider refund reference')
    conn.execute('BEGIN IMMEDIATE')
    try:
        row=conn.execute('SELECT state FROM refund_requests WHERE id=?',(refund_id,)).fetchone()
        if not row: raise RefundError('Unknown refund')
        if row['state']=='refunded':
            previous=conn.execute('SELECT provider_ref FROM refund_requests WHERE id=?',(refund_id,)).fetchone()[0]
            if previous!=provider_ref: raise RefundError('Refund reference mismatch')
            conn.commit();return False
        if row['state']!='approved': raise RefundError('Refund not approved')
        conn.execute('UPDATE refund_requests SET state=?,provider_ref=?,updated=? WHERE id=?',('refunded',provider_ref,timestamp(),refund_id))
        # Revoke order-level access only after the gateway confirms the entire paid
        # amount has actually been refunded. Partial refunds retain their rights
        # pending a product-specific policy; never infer full refund from approval.
        order=conn.execute('SELECT order_id,attempt_id FROM refund_requests WHERE id=?',(refund_id,)).fetchone()
        paid=conn.execute('SELECT amount_cents FROM payment_attempts WHERE id=?',(order['attempt_id'],)).fetchone()
        refunded=conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM refund_requests WHERE attempt_id=? AND state='refunded'",(order['attempt_id'],)).fetchone()[0]
        if paid and refunded >= paid['amount_cents']:
            conn.execute("UPDATE orders SET status='Refunded' WHERE id=?",(order['order_id'],))
        conn.execute('INSERT INTO refund_events(refund_id,actor_id,event,created) VALUES(?,?,?,?)',(refund_id,None,'gateway_refund_verified',timestamp()))
        conn.commit();return True
    except Exception:
        conn.rollback();raise
