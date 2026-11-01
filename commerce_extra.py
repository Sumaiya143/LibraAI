"""Optional bKash tokenized checkout; no local simulation of a successful payment."""
import os,json,urllib.request,urllib.error
from decimal import Decimal

def configured():
 return all(os.getenv(k) for k in ('BKASH_APP_KEY','BKASH_APP_SECRET','BKASH_USERNAME','BKASH_PASSWORD','PUBLIC_BASE_URL'))
def api(path,payload,token=None):
 host='https://tokenized.pay.bka.sh/v1.2.0-beta' if os.getenv('BKASH_LIVE')=='1' else 'https://tokenized.sandbox.bka.sh/v1.2.0-beta'
 headers={'Content-Type':'application/json','Accept':'application/json','X-APP-Key':os.getenv('BKASH_APP_KEY','')}
 if token:headers['Authorization']=token
 else:headers.update({'username':os.getenv('BKASH_USERNAME',''),'password':os.getenv('BKASH_PASSWORD','')})
 req=urllib.request.Request(host+path,data=json.dumps(payload).encode(),headers=headers)
 with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)
def token():
 r=api('/tokenized/checkout/token/grant',{'app_key':os.getenv('BKASH_APP_KEY',''),'app_secret':os.getenv('BKASH_APP_SECRET','')})
 if not r.get('id_token'):raise ValueError('bKash token not issued')
 return r['id_token']
def create(reference,amount):
 t=token();r=api('/tokenized/checkout/create',{'mode':'0011','payerReference':reference,'callbackURL':os.environ['PUBLIC_BASE_URL'].rstrip('/')+'/payment/bkash/callback','amount':str(Decimal(str(amount)).quantize(Decimal('.01'))),'currency':'BDT','intent':'sale','merchantInvoiceNumber':reference},t)
 if not r.get('bkashURL') or not r.get('paymentID'):raise ValueError('bKash did not create payment')
 return {'checkout_url':r['bkashURL'],'payment_id':r['paymentID']}
def execute(payment_id):return api('/tokenized/checkout/execute',{'paymentID':payment_id},token())
def query(payment_id):return api('/tokenized/checkout/payment/status',{'paymentID':payment_id},token())
