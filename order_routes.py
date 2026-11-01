"""Additional account order-management endpoints. Existing routes are unchanged."""
from flask import Blueprint, jsonify, session, request, abort
from order_lifecycle import cancel_unpaid_order, OrderLifecycleError

orders_bp=Blueprint('order_lifecycle', __name__)

@orders_bp.post('/api/orders/<int:order_id>/cancel')
def cancel_order(order_id):
    from app import db, current_user
    user=current_user()
    if not user: abort(401)
    conn=db()
    try:
        changed=cancel_unpaid_order(conn,order_id,user['id'],user['role']=='admin')
        return jsonify({'order_id':order_id,'cancelled':True,'changed':changed,'refund_issued':False})
    except OrderLifecycleError as exc:
        return jsonify({'error':str(exc)}),400
    finally:
        conn.close()

@orders_bp.get('/api/orders/<int:order_id>/history')
def order_history(order_id):
    from app import db, current_user
    user=current_user()
    if not user: abort(401)
    conn=db()
    try:
        order=conn.execute('SELECT user_id FROM orders WHERE id=?',(order_id,)).fetchone()
        if not order: abort(404)
        if order['user_id']!=user['id'] and user['role']!='admin': abort(403)
        events=conn.execute('SELECT event,created FROM order_events WHERE order_id=? ORDER BY id',(order_id,)).fetchall()
        return jsonify({'order_id':order_id,'events':[dict(e) for e in events]})
    finally:
        conn.close()
