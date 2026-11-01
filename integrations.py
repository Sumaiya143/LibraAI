"""Optional production integrations. No payment is marked successful without gateway validation."""
import os,json,urllib.request,urllib.parse,hashlib,hmac,secrets

def ai_reply(question,context=''):
    key=os.getenv('OPENAI_API_KEY','')
    if not key: return {'configured':False,'error':'Set OPENAI_API_KEY on the server to enable real AI responses.'}
    payload=json.dumps({'model':os.getenv('OPENAI_MODEL','gpt-4o-mini'),'messages':[{'role':'system','content':'You are a helpful reading and study assistant. Use supplied excerpts only if relevant. Never claim to have read a book you have not received.'},{'role':'user','content':('Excerpt: '+context[:8000]+'\nQuestion: '+question[:2000])}],'max_tokens':500}).encode()
    req=urllib.request.Request('https://api.openai.com/v1/chat/completions',data=payload,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=25) as r: result=json.load(r)
        return {'configured':True,'answer':result['choices'][0]['message']['content']}
    except Exception: return {'configured':True,'error':'AI provider request failed. Check server logs and credentials.'}

def sslcommerz_start(order_id,amount,currency,customer_email):
    store=os.getenv('SSLCZ_STORE_ID','');password=os.getenv('SSLCZ_STORE_PASSWORD','');base=os.getenv('PUBLIC_BASE_URL','')
    if not (store and password and base.startswith('https://')):return {'error':'Configure SSLCZ_STORE_ID, SSLCZ_STORE_PASSWORD and HTTPS PUBLIC_BASE_URL.'}
    host='https://securepay.sslcommerz.com' if os.getenv('SSLCZ_LIVE')=='1' else 'https://sandbox.sslcommerz.com'
    data={'store_id':store,'store_passwd':password,'total_amount':str(amount),'currency':currency,'tran_id':order_id,'success_url':base+'/payment/return','fail_url':base+'/payment/return','cancel_url':base+'/payment/return','ipn_url':base+'/api/payments/ipn','cus_name':'LibraAI customer','cus_email':customer_email,'cus_add1':'Bangladesh','cus_city':'Dhaka','cus_country':'Bangladesh','cus_phone':'01000000000','shipping_method':'NO','product_name':'Digital book','product_category':'Digital goods','product_profile':'non-physical-goods'}
    try:
        req=urllib.request.Request(host+'/gwprocess/v4/api.php',data=urllib.parse.urlencode(data).encode())
        with urllib.request.urlopen(req,timeout=20) as r: response=json.load(r)
        url=response.get('GatewayPageURL','')
        if not url.startswith('https://'):return {'error':'Payment provider did not return a checkout URL'}
        return {'checkout_url':url,'transaction_id':order_id}
    except Exception:return {'error':'Payment provider unavailable. Order remains pending.'}

def sslcommerz_validate(val_id):
    store=os.getenv('SSLCZ_STORE_ID','');password=os.getenv('SSLCZ_STORE_PASSWORD','')
    if not store or not password or not val_id:return None
    host='https://securepay.sslcommerz.com' if os.getenv('SSLCZ_LIVE')=='1' else 'https://sandbox.sslcommerz.com'
    params=urllib.parse.urlencode({'val_id':val_id,'store_id':store,'store_passwd':password,'v':1,'format':'json'})
    try:
        with urllib.request.urlopen(host+'/validator/api/validationserverAPI.php?'+params,timeout=20) as r:return json.load(r)
    except Exception:return None
