"""Server-side SSLCommerz and bKash tokenized checkout adapters (BDT only).
Never trust redirect or IPN data alone. HTTPS endpoints configurable only by environment.
"""
import json, os, urllib.parse, urllib.request
from decimal import Decimal
from payment_engine import PaymentError, cents

class GatewayError(PaymentError): pass

MAX_GATEWAY_RESPONSE_BYTES = 1024 * 1024

def _reject_duplicate_json_keys(pairs):
    """Reject ambiguous gateway JSON instead of silently accepting the last value."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON object key')
        result[key] = value
    return result

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never forward merchant credentials or tokens across an HTTP redirect."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def request_json(url, data=None, headers=None, form=False):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise GatewayError('Gateway HTTPS URL required')
    if parsed.fragment:
        raise GatewayError('Gateway URL fragments are not allowed')
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()
    h={'Accept':'application/json', **(headers or {})}
    if body is not None: h.setdefault('Content-Type','application/x-www-form-urlencoded' if form else 'application/json')
    try:
        opener = urllib.request.build_opener(_NoRedirect())
        with opener.open(urllib.request.Request(url,data=body,headers=h),timeout=15) as r:
            if r.status < 200 or r.status >= 300: raise GatewayError('Gateway HTTP failure')
            raw = r.read(MAX_GATEWAY_RESPONSE_BYTES + 1)
            if len(raw) > MAX_GATEWAY_RESPONSE_BYTES:
                raise GatewayError('Gateway response exceeds size limit')
            result = json.loads(raw, object_pairs_hook=_reject_duplicate_json_keys)
            if not isinstance(result, dict):
                raise GatewayError('Gateway returned invalid JSON object')
            return result
    except GatewayError:
        raise
    except (OSError,ValueError,KeyError) as e: raise GatewayError('Gateway request failed') from e

def _trusted_checkout_url(value, expected_host=None, allowed_suffix=None, allowed_hosts=None):
    """Validate a gateway-provided checkout URL before redirecting customers.

    HTTPS alone is insufficient: reject userinfo, nonstandard ports, fragments,
    malformed hostnames, and hosts outside the configured provider boundary.
    """
    if not isinstance(value, str) or not value or len(value) > 4096:
        return False
    try:
        parsed = urllib.parse.urlsplit(value)
        host = parsed.hostname
        port = parsed.port  # Access may raise ValueError for malformed ports.
        if (parsed.scheme.lower() != 'https' or not host or
                parsed.username is not None or parsed.password is not None or
                port not in (None, 443) or parsed.fragment or
                not parsed.path.startswith('/') or '\\' in parsed.netloc):
            return False
        host = host.rstrip('.').lower()
        # Reject malformed/ambiguous DNS names rather than trying to repair them.
        if not host or host.startswith('.') or '..' in host or any(ch.isspace() for ch in host):
            return False
        host.encode('idna')
        if expected_host is not None and host != expected_host.lower():
            return False
        if allowed_hosts is not None and host not in {item.lower() for item in allowed_hosts}:
            return False
        if allowed_suffix is not None and not host.endswith('.' + allowed_suffix.lower()):
            return False
        return True
    except (ValueError, UnicodeError):
        return False


def ssl_base():
    return 'https://sandbox.sslcommerz.com' if os.getenv('SSLCOMMERZ_SANDBOX','true').lower()=='true' else 'https://securepay.sslcommerz.com'

def ssl_init(attempt, customer, public_base):
    store=os.getenv('SSLCOMMERZ_STORE_ID');password=os.getenv('SSLCOMMERZ_STORE_PASSWORD')
    if not store or not password: raise GatewayError('SSLCommerz credentials missing')
    amount=f"{Decimal(attempt['amount_cents'])/100:.2f}"
    payload={'store_id':store,'store_passwd':password,'total_amount':amount,'currency':'BDT',
      'tran_id':attempt['merchant_ref'],'success_url':public_base+'/payments/sslcommerz/return',
      'fail_url':public_base+'/payments/sslcommerz/return','cancel_url':public_base+'/payments/sslcommerz/return',
      'ipn_url':public_base+'/payments/sslcommerz/ipn','shipping_method':'NO',
      'product_name':'LibraAI order '+str(attempt['order_id']),'product_category':'Books','product_profile':'general',
      'cus_name':customer.get('name') or 'Customer','cus_email':customer.get('email') or 'unknown@example.com',
      'cus_add1':'Digital order','cus_city':'Dhaka','cus_country':'Bangladesh','cus_phone':'00000000000'}
    r=request_json(ssl_base()+'/gwprocess/v4/api.php',payload,form=True)
    url=r.get('GatewayPageURL')
    expected_host = urllib.parse.urlsplit(ssl_base()).hostname
    if r.get('status')!='SUCCESS' or not _trusted_checkout_url(url, expected_host=expected_host):
        raise GatewayError('SSLCommerz session creation rejected')
    return {'url':url,'provider_ref':r.get('sessionkey') or None}

def ssl_verify(val_id):
    if not val_id or len(val_id)>250: raise GatewayError('Missing validation ID')
    store=os.getenv('SSLCOMMERZ_STORE_ID');password=os.getenv('SSLCOMMERZ_STORE_PASSWORD')
    if not store or not password: raise GatewayError('SSLCommerz credentials missing')
    url=ssl_base()+'/validator/api/validationserverAPI.php?'+urllib.parse.urlencode({'val_id':val_id,'store_id':store,'store_passwd':password,'v':1,'format':'json'})
    return request_json(url)

def bkash_base():
    return 'https://tokenized.sandbox.bka.sh/v1.2.0-beta' if os.getenv('BKASH_SANDBOX','true').lower()=='true' else 'https://tokenized.pay.bka.sh/v1.2.0-beta'

def bkash_token():
    username=os.getenv('BKASH_USERNAME');password=os.getenv('BKASH_PASSWORD')
    app_key=os.getenv('BKASH_APP_KEY');app_secret=os.getenv('BKASH_APP_SECRET')
    if not all((username,password,app_key,app_secret)): raise GatewayError('bKash credentials missing')
    r=request_json(bkash_base()+'/tokenized/checkout/token/grant',{'app_key':app_key,'app_secret':app_secret}, {'username':username,'password':password})
    token=r.get('id_token')
    if not token: raise GatewayError('bKash token rejected')
    return token

def bkash_call(path,payload,token):
    return request_json(bkash_base()+'/tokenized/checkout/'+path,payload,{'Authorization':token,'X-APP-Key':os.environ['BKASH_APP_KEY']})

def bkash_init(attempt,public_base):
    token=bkash_token()
    r=bkash_call('create',{'mode':'0011','payerReference':str(attempt['order_id']),
      'callbackURL':public_base+'/payments/bkash/callback','amount':f"{Decimal(attempt['amount_cents'])/100:.2f}",
      'currency':'BDT','intent':'sale','merchantInvoiceNumber':attempt['merchant_ref']},token)
    # This adapter calls the tokenized API, so accept checkout redirects only
    # from that exact environment's API host. A parent-domain suffix check would
    # also trust unrelated or attacker-controlled subdomains of bka.sh.
    expected_bkash_host = urllib.parse.urlsplit(bkash_base()).hostname
    if (r.get('statusCode')!='0000' or not r.get('paymentID') or
            not _trusted_checkout_url(r.get('bkashURL'), expected_host=expected_bkash_host)):
        raise GatewayError('bKash session creation rejected')
    return {'url':r['bkashURL'],'provider_ref':r['paymentID']}

def bkash_execute_and_query(payment_id):
    token=bkash_token()
    executed=bkash_call('execute',{'paymentID':payment_id},token)
    # An execute response alone is insufficient: confirm independently with query.
    queried=bkash_call('payment/status',{'paymentID':payment_id},token)
    return executed,queried
