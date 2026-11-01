"""Admin shipment updates and customer-visible status; protected by app-wide CSRF middleware."""
from flask import Blueprint, abort, jsonify, request
from shipping_engine import ShippingError, update_shipment

shipping_bp=Blueprint('shipping',__name__)

@shipping_bp.post('/api/admin/orders/<int:order_id>/shipment')
def shipment_update(order_id):
    from app import db,current_user
    user=current_user()
    if not user: abort(401)
    if user['role']!='admin': abort(403)
    data=request.get_json(silent=True)
    if not isinstance(data,dict): return jsonify(error='JSON required'),400
    try:
        with db() as conn:
            changed=update_shipment(conn,order_id,user['id'],data.get('state'),
                                    data.get('carrier',''),data.get('tracking_number',''))
        return jsonify(order_id=order_id,state=data['state'],changed=changed)
    except ShippingError as exc:
        return jsonify(error=str(exc)),409

@shipping_bp.get('/api/orders/<int:order_id>/shipment')
def shipment_status(order_id):
    from app import db,current_user
    user=current_user()
    if not user: abort(401)
    with db() as conn:
        order=conn.execute('SELECT user_id FROM orders WHERE id=?',(order_id,)).fetchone()
        if not order: abort(404)
        if order['user_id']!=user['id'] and user['role']!='admin': abort(403)
        shipment=conn.execute('SELECT state,carrier,tracking_number,updated FROM print_shipments WHERE order_id=?',(order_id,)).fetchone()
    return jsonify(order_id=order_id,shipment=dict(shipment) if shipment else None)

@shipping_bp.get('/api/orders/<int:order_id>/shipment/history')
def shipment_history(order_id):
    """Order-scoped fulfillment audit trail; no cross-customer data exposure."""
    from app import db, current_user
    user=current_user()
    if not user: abort(401)
    with db() as conn:
        order=conn.execute('SELECT user_id FROM orders WHERE id=?',(order_id,)).fetchone()
        if not order: abort(404)
        if order['user_id']!=user['id'] and user['role']!='admin': abort(403)
        rows=conn.execute(
            'SELECT state,created,carrier,tracking_number FROM print_shipment_events WHERE order_id=? ORDER BY id ASC',
            (order_id,)).fetchall()
    return jsonify(order_id=order_id,events=[dict(row) for row in rows])
