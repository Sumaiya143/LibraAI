"""Operator-only gateway reconciliation. Run with --dry-run first.
Never trusts browser return or an IPN alone; verifies with provider APIs.
"""
import argparse, json, sqlite3, os
from urllib.parse import quote
from payment_engine import pending_for_reconciliation, settle_verified, cents, PaymentError, record_reconciliation_event
from payment_providers import ssl_verify, GatewayError, bkash_token, bkash_call

def reconcile_one(conn, attempt, verify_ssl=ssl_verify, query_bkash=None, apply=False):
    if attempt['state']!='pending': return 'skip'
    if attempt['provider']=='sslcommerz':
        # A session ID is not a validation ID. Query by merchant transaction ID.
        from payment_providers import ssl_base, request_json
        from urllib.parse import urlencode
        store=os.environ.get('SSLCOMMERZ_STORE_ID'); password=os.environ.get('SSLCOMMERZ_STORE_PASSWORD')
        if not store or not password: raise GatewayError('SSLCommerz credentials missing')
        url=ssl_base()+'/validator/api/merchantTransIDvalidationAPI.php?'+urlencode(
            {'tran_id':attempt['merchant_ref'],'store_id':store,'store_passwd':password,'format':'json'})
        response=request_json(url) if verify_ssl is ssl_verify else verify_ssl(attempt['merchant_ref'])
        if not isinstance(response, dict): raise PaymentError('Malformed SSLCommerz verification response')
        status=response.get('status')
        if status not in ('VALID','VALIDATED'): return 'pending'
        if response.get('tran_id')!=attempt['merchant_ref']: raise PaymentError('Reference mismatch')
        if response.get('store_id') is not None and response['store_id']!=store: raise PaymentError('Merchant mismatch')
        if str(response.get('risk_level','0'))!='0': raise PaymentError('Risky payment')
        reference=str(response.get('bank_tran_id') or response.get('val_id') or '')
    elif attempt['provider']=='bkash':
        if query_bkash is None:
            token=bkash_token()
            response=bkash_call('payment/status',{'paymentID':attempt['provider_ref']},token)
        else: response=query_bkash(attempt['provider_ref'])
        if not isinstance(response, dict): raise PaymentError('Malformed bKash verification response')
        if response.get('transactionStatus')!='Completed' or response.get('statusCode')!='0000': return 'pending'
        if response.get('paymentID')!=attempt['provider_ref']: raise PaymentError('Payment ID mismatch')
        if response.get('merchantInvoiceNumber')!=attempt['merchant_ref']: raise PaymentError('Invoice mismatch')
        reference=attempt['provider_ref']
    else: raise PaymentError('Unsupported provider')
    if response.get('currency')!='BDT' or cents(response.get('amount'))!=attempt['amount_cents']:
        raise PaymentError('Amount or currency mismatch')
    if not reference: raise PaymentError('Missing transaction reference')
    if not apply: return 'verified_dry_run'
    changed=settle_verified(conn,attempt['merchant_ref'],attempt['provider'],reference,
                            cents(response['amount']),'BDT',True,response.get('status') or response.get('transactionStatus'))
    return 'settled' if changed else 'already_settled'

def main():
    parser=argparse.ArgumentParser(description='Reconcile unsettled LibraAI payments')
    parser.add_argument('--db',default=os.getenv('LIBRAAI_DB_PATH','libraai.db'))
    parser.add_argument('--limit',type=int,default=100)
    parser.add_argument('--apply',action='store_true',help='Write verified settlements (default dry-run)')
    parser.add_argument('--strict',action='store_true',help='Exit with status 2 when a payment remains unresolved')
    parser.add_argument('--summary',action='store_true',help='Emit machine-readable batch totals')
    args=parser.parse_args()
    if args.limit < 1 or args.limit > 500:
        parser.error('--limit must be between 1 and 500')
    if not os.path.isfile(args.db):
        parser.error('Database file does not exist; refusing to create an empty database')
    # Dry runs open SQLite in read-only mode so they cannot mutate financial data.
    mode = 'rw' if args.apply else 'ro'
    conn=sqlite3.connect('file:'+quote(os.path.abspath(args.db),safe='/')+'?mode='+mode, uri=True)
    conn.row_factory=sqlite3.Row
    totals = {'processed': 0, 'settled': 0, 'already_settled': 0, 'verified_dry_run': 0, 'pending': 0, 'manual_review': 0, 'skip': 0}
    try:
        for attempt in pending_for_reconciliation(conn,args.limit):
            try: result=reconcile_one(conn,attempt,apply=args.apply)
            except (PaymentError,GatewayError,ValueError) as exc:
                result='manual_review'
                if args.apply: record_reconciliation_event(conn,attempt['merchant_ref'],'manual_review',type(exc).__name__)
            totals['processed'] += 1
            totals[result] = totals.get(result, 0) + 1
            print(json.dumps({'merchant_ref':attempt['merchant_ref'],'provider':attempt['provider'],'result':result}))
    finally: conn.close()
    if args.summary:
        print(json.dumps({'type': 'reconciliation_summary', 'mode': 'apply' if args.apply else 'dry_run', **totals}))
    # A successful process launch must not be mistaken for successful settlement.
    if args.strict and (totals['pending'] or totals['manual_review'] or totals['skip']):
        raise SystemExit(2)
if __name__=='__main__': main()
