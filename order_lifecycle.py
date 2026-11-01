"""Safe sandbox order cancellation and stock restoration.

This module does not issue refunds or communicate with payment processors.
"""
from datetime import datetime, timezone

class OrderLifecycleError(ValueError):
    pass


def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS order_events (
        id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, actor_id INTEGER NOT NULL,
        event TEXT NOT NULL, created TEXT NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id))''')
    conn.commit()


def cancel_unpaid_order(conn, order_id, actor_id, is_admin=False):
    """Idempotently cancel an unpaid sandbox order and return reserved inventory once."""
    conn.execute('BEGIN IMMEDIATE')
    try:
        order = conn.execute('SELECT id,user_id,status FROM orders WHERE id=?', (order_id,)).fetchone()
        if order is None:
            raise OrderLifecycleError('Order not found')
        oid, owner, status = order
        if owner != actor_id and not is_admin:
            raise OrderLifecycleError('Not authorized')
        if status == 'Cancelled — sandbox':
            conn.commit()
            return False
        if status != 'Awaiting payment — sandbox only':
            raise OrderLifecycleError('Only unpaid sandbox orders can be cancelled')
        items = conn.execute('SELECT book_id,quantity FROM order_items WHERE order_id=?', (oid,)).fetchall()
        if not items:
            raise OrderLifecycleError('Order items missing; manual reconciliation required')
        for bid, quantity in items:
            if quantity <= 0:
                raise OrderLifecycleError('Invalid order item quantity')
            if conn.execute('UPDATE books SET stock=stock+? WHERE id=?', (quantity,bid)).rowcount != 1:
                raise OrderLifecycleError('Book missing; manual reconciliation required')
        conn.execute('UPDATE orders SET status=? WHERE id=?', ('Cancelled — sandbox', oid))
        conn.execute('INSERT INTO order_events(order_id,actor_id,event,created) VALUES(?,?,?,?)',
                     (oid,actor_id,'cancelled_unpaid',datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
