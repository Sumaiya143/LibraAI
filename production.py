"""Run with python production.py. Integrations are opt-in and payment verification is server-side."""
import os,json,sqlite3,secrets,urllib.parse
from decimal import Decimal,InvalidOperation
from http.server import ThreadingHTTPServer
from advanced import Advanced,setup,files_setup,db
from integrations import ai_reply,sslcommerz_start,sslcommerz_validate
from ssl_payment_integrity import reconcile_sslcommerz

def migrate():
 setup();files_setup()
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS payment_attempts(id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL,transaction_id TEXT UNIQUE NOT NULL,provider TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'initiated',validation_id TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP); CREATE TABLE IF NOT EXISTS payment_events(id INTEGER PRIMARY KEY,transaction_id TEXT,event TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP); CREATE TABLE IF NOT EXISTS merchant_payouts(id INTEGER PRIMARY KEY,merchant_id INTEGER,amount TEXT,currency TEXT,status TEXT DEFAULT 'manual_review',created TEXT DEFAULT CURRENT_TIMESTAMP);''')

class Production(Advanced):
 def do_GET(self):
  p=urllib.parse.urlparse(self.path)
  if p.path=='/api/integrations/status':return self.send(200,{'ai':bool(os.getenv('OPENAI_API_KEY')),'sslcommerz':bool(os.getenv('SSLCZ_STORE_ID') and os.getenv('SSLCZ_STORE_PASSWORD') and os.getenv('PUBLIC_BASE_URL')),'bkash':False,'payouts':'manual_review_only','subscriptions':'not_enabled'})
  if p.path=='/payment/return':
   self.send_response(303);self.send_header('Location','/?payment=check-order-status');self.end_headers();return
  return super().do_GET()
 def do_POST(self):
  p=urllib.parse.urlparse(self.path).path
  if p=='/api/ai/chat':
   u=self.user()
   if not u:return self.send(401,{'error':'Sign in required'})
   b=self.body();q=str(b.get('question','')).strip();context=str(b.get('context',''))
   if not 1<=len(q)<=2000:return self.send(400,{'error':'Question must be 1-2000 characters'})
   result=ai_reply(q,context);return self.send(200 if 'answer' in result else 503,result)
  if p=='/api/payments/start':
   u=self.user()
   if not u:return self.send(401,{'error':'Sign in required'})
   b=self.body()
   try:oid=int(b.get('order_id'))
   except:return self.send(400,{'error':'Invalid order'})
   with db() as c:
    order=c.execute('SELECT id,user_id,amount,status FROM orders WHERE id=? AND user_id=?',(oid,u['id'])).fetchone()
    if not order:return self.send(404,{'error':'Order not found'})
    if order['status']!='pending':return self.send(409,{'error':'Order not pending'})
    amount=Decimal(str(order['amount'])).quantize(Decimal('0.01'))
    if amount<=0:return self.send(400,{'error':'Invalid payable amount'})
    tid='LIBRA-'+str(oid)+'-'+secrets.token_hex(8)
    result=sslcommerz_start(tid,amount,'BDT',u['email'])
    if 'error' in result:return self.send(503,result)
    c.execute('INSERT INTO payment_attempts(order_id,transaction_id,provider) VALUES(?,?,?)',(oid,tid,'sslcommerz'))
   return self.send(200,result)
  if p=='/api/payments/ipn':
   # An IPN is not proof of payment; validate transaction with provider before fulfillment.
   try:length=int(self.headers.get('Content-Length','0'))
   except (ValueError,TypeError):return self.send(400,{'error':'Invalid payload size'})
   if length<1 or length>16384:return self.send(400,{'error':'Invalid payload size'})
   raw=self.rfile.read(length)
   try:data=urllib.parse.parse_qs(raw.decode(),strict_parsing=False);tid=data.get('tran_id',[''])[0];val=data.get('val_id',[''])[0]
   except:return self.send(400,{'error':'Invalid IPN'})
   if not tid or not val:return self.send(400,{'error':'Missing transaction reference'})
   with db() as c:
    attempt=c.execute('SELECT * FROM payment_attempts WHERE transaction_id=?',(tid,)).fetchone()
    if not attempt:return self.send(404,{'error':'Unknown transaction'})
   result=sslcommerz_validate(val)
   try:
    with db() as c:
     outcome=reconcile_sslcommerz(c,tid,val,result)
   except (ValueError,LookupError):return self.send(400,{'error':'Gateway verification mismatch'})
   except (RuntimeError,sqlite3.IntegrityError):return self.send(409,{'error':'Payment reconciliation conflict'})
   return self.send(200,{'ok':True,'duplicate':outcome=='duplicate'})
  return super().do_POST()
if __name__=='__main__':
 migrate();port=int(os.getenv('PORT','8000'));print(f'LibraAI integrated server: http://127.0.0.1:{port}');ThreadingHTTPServer(('127.0.0.1',port),Production).serve_forever()
