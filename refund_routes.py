"""Customer refund request and admin review; actual gateway refund execution intentionally not exposed."""
from flask import Blueprint, request, jsonify, abort
from refund_engine import request_refund, review_refund, RefundError

refunds_bp=Blueprint('refunds',__name__)

@refunds_bp.post('/api/refunds/request')
def request_customer_refund():
    from app import db,current_user
    user=current_user()
    if not user: abort(401)
    data=request.get_json(silent=True)
    if not isinstance(data,dict): return jsonify(error='JSON required'),400
    try:
        order_id=data.get('order_id'); amount=data.get('amount_cents')
        if type(order_id) is not int or order_id<=0: raise RefundError('Invalid order')
        with db() as conn:
            refund_id=request_refund(conn,order_id,user['id'],amount,data.get('reason',''),item_id=data.get('item_id'))
        return jsonify(refund_id=refund_id,status='requested',note='Request only; no money has been refunded'),201
    except RefundError as exc: return jsonify(error=str(exc)),400

@refunds_bp.post('/api/admin/refunds/<int:refund_id>/review')
def admin_review_refund(refund_id):
    from app import db,current_user
    user=current_user()
    if not user: abort(401)
    if user['role']!='admin': abort(403)
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or type(data.get('approve')) is not bool: return jsonify(error='approve boolean required'),400
    try:
        with db() as conn: review_refund(conn,refund_id,user['id'],data['approve'],admin=True)
        return jsonify(refund_id=refund_id,status='approved' if data['approve'] else 'rejected',note='Approval does not execute gateway refund')
    except RefundError as exc: return jsonify(error=str(exc)),409

@refunds_bp.get('/api/refunds/orders/<int:order_id>')
def list_order_refunds(order_id):
    from app import db,current_user
    user=current_user()
    if not user: abort(401)
    with db() as conn:
        order=conn.execute('SELECT user_id FROM orders WHERE id=?',(order_id,)).fetchone()
        if not order: abort(404)
        if order['user_id']!=user['id'] and user['role']!='admin': abort(403)
        rows=conn.execute('SELECT id,amount_cents,reason,state,created,updated FROM refund_requests WHERE order_id=? ORDER BY id DESC',(order_id,)).fetchall()
    return jsonify(order_id=order_id,refunds=[dict(row) for row in rows])

@refunds_bp.get('/api/admin/refunds/queue')
def admin_refund_queue():
    """Admin-only, bounded refund triage list; no customer PII or payment credentials."""
    from app import db, current_user
    from refund_queue import list_refund_queue
    user = current_user()
    if not user: abort(401)
    if user['role'] != 'admin': abort(403)
    try:
        limit = request.args.get('limit', '50')
        offset = request.args.get('offset', '0')
        # Reject signs, decimals, whitespace, or arbitrarily long numeric strings.
        if not limit.isascii() or not limit.isdecimal() or len(limit) > 3:
            raise RefundError('Invalid limit')
        if not offset.isascii() or not offset.isdecimal() or len(offset) > 7:
            raise RefundError('Invalid offset')
        with db() as conn:
            result = list_refund_queue(conn, state=request.args.get('state', 'requested'),
                                       limit=int(limit), offset=int(offset))
        return jsonify(result)
    except RefundError as exc:
        return jsonify(error=str(exc)), 400

@refunds_bp.get('/api/admin/refunds/queue.csv')
def admin_refund_queue_csv():
    """Download one bounded page of the admin queue; no customer PII or gateway refs."""
    from app import db, current_user
    from refund_queue import list_refund_queue
    from refund_queue_csv import queue_page_csv
    from flask import Response
    user = current_user()
    if not user: abort(401)
    if user['role'] != 'admin': abort(403)
    try:
        limit = request.args.get('limit', '50')
        offset = request.args.get('offset', '0')
        if not limit.isascii() or not limit.isdecimal() or len(limit) > 3:
            raise RefundError('Invalid limit')
        if not offset.isascii() or not offset.isdecimal() or len(offset) > 7:
            raise RefundError('Invalid offset')
        with db() as conn:
            report = list_refund_queue(conn, state=request.args.get('state', 'requested'),
                                       limit=int(limit), offset=int(offset))
        return Response(queue_page_csv(report), content_type='text/csv; charset=utf-8',
                        headers={'Content-Disposition': 'attachment; filename="refund-queue.csv"',
                                 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
    except RefundError as exc:
        return jsonify(error=str(exc)), 400
