"""Auditable manual print-order fulfillment; never invents a carrier shipment."""
from datetime import datetime, timezone

class ShippingError(ValueError):
    pass

def now():
    return datetime.now(timezone.utc).isoformat()

def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS print_shipments (
      order_id INTEGER PRIMARY KEY REFERENCES orders(id),
      state TEXT NOT NULL CHECK(state IN ('packing','dispatched','delivered')),
      carrier TEXT, tracking_number TEXT, updated TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS print_shipment_events (
      id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
      actor_id INTEGER NOT NULL, state TEXT NOT NULL,
      created TEXT NOT NULL, carrier TEXT, tracking_number TEXT)''')
    # Upgrade existing SQLite installations without dropping shipment history.
    columns={row[1] for row in conn.execute('PRAGMA table_info(print_shipment_events)')}
    for name in ('carrier','tracking_number'):
        if name not in columns:
            conn.execute(f'ALTER TABLE print_shipment_events ADD COLUMN {name} TEXT')
    conn.commit()

def update_shipment(conn, order_id, actor_id, state, carrier='', tracking_number=''):
    if type(order_id) is not int or order_id < 1 or type(actor_id) is not int or actor_id < 1:
        raise ShippingError('Invalid order or actor')
    if state not in ('packing','dispatched','delivered'):
        raise ShippingError('Invalid shipment state')
    if not isinstance(carrier,str) or not isinstance(tracking_number,str) or len(carrier)>100 or len(tracking_number)>120:
        raise ShippingError('Invalid carrier or tracking number')
    carrier, tracking_number=carrier.strip(),tracking_number.strip()
    if state=='dispatched' and (not carrier or not tracking_number):
        raise ShippingError('Carrier and tracking number required for dispatch')
    conn.execute('BEGIN IMMEDIATE')
    try:
        order=conn.execute('SELECT status,address FROM orders WHERE id=?',(order_id,)).fetchone()
        if not order: raise ShippingError('Order not found')
        paid=conn.execute("SELECT 1 FROM payment_attempts WHERE order_id=? AND state='paid'",(order_id,)).fetchone()
        if not paid or order['status'] in ('Refunded','Cancelled','Cancelled — unpaid'):
            raise ShippingError('Verified paid, non-refunded order required')
        if not order['address'] or not order['address'].strip():
            raise ShippingError('Shipping address required')
        items=conn.execute('SELECT format FROM order_items WHERE order_id=?',(order_id,)).fetchall()
        if not items or not any(str(i['format']).lower()=='print' for i in items):
            raise ShippingError('Order contains no print books')
        old=conn.execute('SELECT state,carrier,tracking_number FROM print_shipments WHERE order_id=?',(order_id,)).fetchone()
        previous=old['state'] if old else None
        transitions={None:('packing',),'packing':('dispatched',),'dispatched':('delivered',),'delivered':()}
        if previous==state:
            # Retries are idempotent only if they do not silently rewrite
            # the carrier/tracking details of an existing dispatch.
            if state=='dispatched' and (carrier!=old['carrier'] or tracking_number!=old['tracking_number']):
                raise ShippingError('Dispatch details cannot change through a retry')
            conn.commit(); return False
        if state not in transitions[previous]: raise ShippingError('Invalid shipment transition')
        if old and state=='delivered':
            carrier,tracking_number=old['carrier'],old['tracking_number']
        conn.execute('''INSERT INTO print_shipments(order_id,state,carrier,tracking_number,updated)
          VALUES(?,?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET
          state=excluded.state,carrier=excluded.carrier,tracking_number=excluded.tracking_number,updated=excluded.updated''',
          (order_id,state,carrier or None,tracking_number or None,now()))
        conn.execute('INSERT INTO print_shipment_events(order_id,actor_id,state,created,carrier,tracking_number) VALUES(?,?,?,?,?,?)',
                     (order_id,actor_id,state,now(),carrier or None,tracking_number or None))
        conn.commit(); return True
    except Exception:
        conn.rollback();raise
