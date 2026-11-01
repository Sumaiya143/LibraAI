"""Secure checkout initiation, gateway notification and customer order status."""
import os, secrets
from urllib.parse import urlsplit
from flask import Blueprint, request, jsonify, abort, redirect
from payment_engine import setup, create_attempt, mark_pending, settle_verified, cents, PaymentError, abandon_unlaunched_attempt
from payment_providers import ssl_init, ssl_verify, bkash_init, bkash_execute_and_query, GatewayError

payments_bp=Blueprint('payments',__name__)

@payments_bp.get('/api/payments/readiness')
def public_payment_readiness():
    """Return safe provider configuration flags; never return credential values."""
    ssl_required = ('SSLCOMMERZ_STORE_ID', 'SSLCOMMERZ_STORE_PASSWORD')
    bkash_required = ('BKASH_USERNAME', 'BKASH_PASSWORD', 'BKASH_APP_KEY', 'BKASH_APP_SECRET')
    def configured(names):
        return all(bool(os.getenv(name, '').strip()) for name in names)
    providers = {
        'sslcommerz': {'configured': configured(ssl_required), 'sandbox': os.getenv('SSLCOMMERZ_SANDBOX', 'true').lower() == 'true'},
        'bkash': {'configured': configured(bkash_required), 'sandbox': os.getenv('BKASH_SANDBOX', 'true').lower() == 'true'},
    }
    missing = [name for name, item in providers.items() if not item['configured']]
    return jsonify({'ready': not missing, 'providers': providers, 'missing_providers': missing,
                    'live_transactions_verified': os.getenv('LIBRAAI_LIVE_PAYMENT_E2E_VERIFIED', 'no').lower() == 'yes',
                    'message': 'Merchant credentials and verified provider transactions are required before live payments can be accepted.'}), 200

from payment_origin import validate_public_origin

def public_base():
    return validate_public_origin(os.getenv('LIBRAAI_PUBLIC_URL', ''))

def lookup(ref):
    from app import db
    with db() as c:
        r=c.execute('SELECT * FROM payment_attempts WHERE merchant_ref=?',(ref,)).fetchone()
        return dict(r) if r else None

@payments_bp.post('/pay/<int:order_id>/<provider>')
def payment_form(order_id,provider):
    from app import current_user
    if not current_user(): abort(401)
    if provider not in ('sslcommerz','bkash'): abort(404)
    # Same CSRF-checked initiation and provider verification path as JSON API.
    result, status_code = initiate(order_id,provider,current_user())
    if status_code in (200,201):
        return redirect(result['checkout_url'],303)
    return jsonify(result),status_code

def initiate(oid,provider,user):
    from app import db
    from commercial_readiness import inspect
    if not inspect()['ready']:
        return {'error':'Commercial payment disabled until launch checks pass'},503
    try:
        with db() as c: attempt,created=create_attempt(c,oid,user['id'],provider,'LIBRA-'+secrets.token_hex(16))
        if attempt['provider']!=provider: return {'error':'Existing attempt uses another gateway'},409
        if attempt['state']=='paid': return {'error':'Order already paid'},409
        if attempt['state']=='pending' and attempt['gateway_url']:
            return {'order_id':oid,'provider':provider,'checkout_url':attempt['gateway_url']},200
        customer={'name':user['name'],'email':user['email']}
        gateway=ssl_init(attempt,customer,public_base()) if provider=='sslcommerz' else bkash_init(attempt,public_base())
        with db() as c: mark_pending(c,attempt['merchant_ref'],gateway['provider_ref'],gateway['url'])
        return {'order_id':oid,'provider':provider,'checkout_url':gateway['url']},201
    except GatewayError as e:
        message = str(e)
        if 'credentials missing' in message.lower():
            return {'error':'Merchant credentials are not configured yet. Live payment setup is pending.',
                    'code':'merchant_credentials_required','provider':provider},503
        return {'error':'Payment provider could not initialize a secure checkout session.', 'code':'gateway_unavailable'},502
    except PaymentError as e:
        return {'error':str(e)},400

@payments_bp.post('/api/payments/abandon-unlaunched')
def abandon_unlaunched():
    """Switch payment providers only if no external gateway session exists."""
    from app import current_user, db
    user = current_user()
    if not user: abort(401)
    data = request.get_json(silent=True)
    if not isinstance(data, dict): return jsonify(error='JSON body required'), 400
    oid, ref = data.get('order_id'), data.get('merchant_ref')
    if type(oid) is not int or oid <= 0 or not isinstance(ref, str) or not ref or len(ref)>160:
        return jsonify(error='Invalid order or payment reference'), 400
    try:
        with db() as c: abandon_unlaunched_attempt(c, oid, user['id'], ref)
        return jsonify(status='abandoned', order_id=oid), 200
    except PaymentError as e:
        return jsonify(error=str(e)), 409

@payments_bp.post('/api/payments/start')
def start():
    from app import current_user
    user=current_user()
    if not user: abort(401)
    data=request.get_json(silent=True)
    if not isinstance(data,dict): return jsonify(error='JSON body required'),400
    oid=data.get('order_id'); provider=data.get('provider')
    if type(oid) is not int or oid<=0: return jsonify(error='Invalid order ID'),400
    response,status_code=initiate(oid,provider,user)
    return jsonify(response),status_code


def process_ssl(data):
    merchant_ref=data.get('tran_id'); val_id=data.get('val_id')
    if not merchant_ref or not val_id: raise PaymentError('Missing gateway identifiers')
    attempt=lookup(merchant_ref)
    if not attempt or attempt['provider']!='sslcommerz': raise PaymentError('Unknown payment')
    verified=ssl_verify(val_id)
    if verified.get('status') not in ('VALID','VALIDATED'): raise PaymentError('Gateway did not verify payment')
    if verified.get('tran_id')!=merchant_ref: raise PaymentError('Transaction reference mismatch')
    # The validation response may omit store_id; reject only a present mismatch.
    if verified.get('store_id') is not None and str(verified['store_id'])!=os.getenv('SSLCOMMERZ_STORE_ID'): raise PaymentError('Merchant mismatch')
    if str(verified.get('risk_level','0'))!='0': raise PaymentError('Risky payment requires manual review')
    if verified.get('currency')!='BDT': raise PaymentError('Currency mismatch')
    with __import__('app').db() as c:
        return settle_verified(c,merchant_ref,'sslcommerz',str(verified.get('bank_tran_id') or verified.get('val_id')),
                               cents(verified.get('amount')),verified.get('currency'),True,verified.get('status'))

@payments_bp.post('/payments/sslcommerz/ipn')
def ssl_ipn():
    # IPN endpoint intentionally bypasses session CSRF, but verifies against gateway server.
    try:
        process_ssl(request.form)
        return 'OK',200
    except (PaymentError,GatewayError): return 'Unverified',400

@payments_bp.route('/payments/sslcommerz/return',methods=['GET','POST'])
def ssl_return():
    # A browser redirect cannot settle a payment; IPN or reconciliation must verify it.
    return redirect('/my/orders?payment=processing',303)

@payments_bp.get('/payments/bkash/callback')
def bkash_callback():
    payment_id=request.args.get('paymentID','')
    if not payment_id or len(payment_id)>160: return redirect('/my/orders?payment=unverified',303)
    from app import db
    with db() as c:
        row=c.execute('SELECT * FROM payment_attempts WHERE provider=? AND provider_ref=?',('bkash',payment_id)).fetchone()
        attempt=dict(row) if row else None
    if not attempt: return redirect('/my/orders?payment=unverified',303)
    if request.args.get('status')!='success': return redirect('/my/orders?payment=processing',303)
    try:
        executed,verified=bkash_execute_and_query(payment_id)
        if executed.get('statusCode')!='0000' or verified.get('statusCode')!='0000': raise PaymentError('bKash verification rejected')
        if verified.get('transactionStatus')!='Completed': raise PaymentError('Payment not completed')
        if verified.get('paymentID')!=payment_id: raise PaymentError('Payment reference mismatch')
        if verified.get('merchantInvoiceNumber')!=attempt['merchant_ref']: raise PaymentError('Invoice mismatch')
        with db() as c:
            settle_verified(c,attempt['merchant_ref'],'bkash',payment_id,cents(verified.get('amount')),verified.get('currency'),True,verified.get('transactionStatus'))
    except (PaymentError,GatewayError): return redirect('/my/orders?payment=unverified',303)
    return redirect('/my/orders?payment=confirmed',303)

@payments_bp.get('/api/payments/orders/<int:order_id>')
def status(order_id):
    from app import db,current_user
    user=current_user()
    if not user: abort(401)
    with db() as c:
        order=c.execute('SELECT id,user_id,status,total FROM orders WHERE id=?',(order_id,)).fetchone()
        if not order: abort(404)
        if order['user_id']!=user['id'] and user['role']!='admin': abort(403)
        attempts=c.execute('SELECT provider,state,created,updated FROM payment_attempts WHERE order_id=? ORDER BY id DESC',(order_id,)).fetchall()
        return jsonify(order_id=order_id,order_status=order['status'],total=order['total'],currency='BDT',payments=[dict(x) for x in attempts])
