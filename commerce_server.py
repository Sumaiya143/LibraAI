"""Additional checkout, subscription invoice and payout reconciliation APIs.
Use python commerce_server.py. Gateway credentials and external callbacks are required.
"""
import os,secrets,urllib.parse,json
from decimal import Decimal,InvalidOperation
from http.server import ThreadingHTTPServer
from production import Production,migrate,db
import commerce_extra as bk
from payment_integrity import reconcile_bkash
from payment_audit import install as install_payment_audit
from payout_review import install as install_payout_review, review as review_payout
from subscription_lifecycle import install as install_subscription_lifecycle, create_invoice, cancel_invoice
from invoice_maintenance import expire_due
from commerce_health import assess as assess_commerce_health
from admin_payouts import list_payouts
from payout_export import render_payout_csv
from payout_full_export import export_snapshot, ExportTooLarge

def setup():
 migrate()
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS bkash_attempts(id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL,user_id INTEGER NOT NULL,reference TEXT UNIQUE NOT NULL,payment_id TEXT UNIQUE NOT NULL,status TEXT NOT NULL DEFAULT 'initiated',created TEXT DEFAULT CURRENT_TIMESTAMP);CREATE TABLE IF NOT EXISTS subscription_invoices(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,plan TEXT NOT NULL,amount TEXT NOT NULL,currency TEXT NOT NULL DEFAULT 'BDT',status TEXT NOT NULL DEFAULT 'unpaid',created TEXT DEFAULT CURRENT_TIMESTAMP);CREATE TABLE IF NOT EXISTS payout_accounts(merchant_id INTEGER PRIMARY KEY,method TEXT NOT NULL,masked_account TEXT NOT NULL,verified INTEGER NOT NULL DEFAULT 0);''')
  columns={row[1] for row in c.execute('PRAGMA table_info(bkash_attempts)')}
  if 'trx_id' not in columns:
   c.execute('ALTER TABLE bkash_attempts ADD COLUMN trx_id TEXT')
  c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_bkash_unique_trx ON bkash_attempts(trx_id)')
  install_payment_audit(c)
  install_payout_review(c)
  install_subscription_lifecycle(c)


def commerce_origin_allowed(origin, host):
 """Reject browser cross-site writes before any commerce side effects."""
 if not origin:
  return True  # Server-to-server clients may omit Origin.
 try:
  parsed=urllib.parse.urlsplit(origin)
  return (parsed.scheme in ('http','https') and bool(parsed.hostname)
          and parsed.netloc == host and not parsed.username and not parsed.password
          and parsed.path in ('','/') and not parsed.query and not parsed.fragment)
 except (ValueError,TypeError):
  return False


def commerce_browser_write_allowed(headers):
 """Defense in depth: reject cross-site browser writes even without Origin.

 Fetch Metadata is supplied by modern browsers; non-browser webhook clients
 may omit it.  Origin checks remain mandatory when an Origin is supplied.
 """
 site=(headers.get('Sec-Fetch-Site') or '').strip().lower()
 if site and site not in ('same-origin','none'):
  return False
 return commerce_origin_allowed(headers.get('Origin'),headers.get('Host',''))


class Commerce(Production):
 def do_GET(self):
  p=urllib.parse.urlparse(self.path)
  # Enforce authorization before serving the dashboard HTML, not just in JS.
  if p.path in ('/admin-commerce.html', '/admin-commerce', '/admin-payouts.html'):
   u=self.user()
   if not u:return self.send(401,{'error':'Sign in required'})
   if u['role']!='admin':return self.send(403,{'error':'Admin access required'})
   if p.path=='/admin-commerce':
    return self.redirect('/admin-commerce.html')
  if p.path=='/payment/bkash/callback':
   q=urllib.parse.parse_qs(p.query);payment_id=q.get('paymentID',[''])[0];state=q.get('status',[''])[0]
   if not payment_id or state!='success':return self.redirect('/integrations.html?payment=not-completed')
   with db() as c:a=c.execute('SELECT * FROM bkash_attempts WHERE payment_id=?',(payment_id,)).fetchone()
   if not a:return self.redirect('/integrations.html?payment=unknown')
   if a['status']=='validated':return self.redirect('/integrations.html?payment=confirmed')
   try:
    r=bk.execute(payment_id)
    if r.get('transactionStatus')!='Completed':r=bk.query(payment_id)
    if r.get('transactionStatus')!='Completed' or r.get('paymentID')!=payment_id:return self.redirect('/integrations.html?payment=unverified')
    with db() as c:
     outcome=reconcile_bkash(c,payment_id,r)
    return self.redirect('/integrations.html?payment='+outcome)
   except Exception:return self.redirect('/integrations.html?payment=verification-failed')
  if p.path=='/api/admin/commerce/payouts/export.csv':
   u=self.user()
   if not u:return self.send(401,{'error':'Sign in required'})
   if u['role']!='admin':return self.send(403,{'error':'Admin access required'})
   try:
    with db() as c:snapshot=export_snapshot(c)
   except ExportTooLarge:return self.send(413,{'error':'Payout audit too large for a single CSV export; no partial export returned'})
   payload=render_payout_csv(snapshot)
   self.send_response(200)
   self.send_header('Content-Type','text/csv; charset=utf-8')
   self.send_header('Content-Disposition','attachment; filename="libraai-payout-audit.csv"')
   self.send_header('Content-Length',str(len(payload)))
   self.send_header('Cache-Control','no-store')
   self.send_header('X-Content-Type-Options','nosniff')
   self.send_header('X-Frame-Options','DENY')
   self.end_headers()
   self.wfile.write(payload)
   return
  if p.path=='/api/admin/commerce/payouts':
   u=self.user()
   if not u:return self.send(401,{'error':'Sign in required'})
   if u['role']!='admin':return self.send(403,{'error':'Admin access required'})
   try:
    params=urllib.parse.parse_qs(p.query)
    raw=params.get('limit',['50'])[0]
    if not raw.isascii() or not raw.isdecimal():raise ValueError('Invalid limit')
    limit=int(raw)
    with db() as c:result=list_payouts(c,limit)
   except ValueError:return self.send(400,{'error':'Limit must be between 1 and 100'})
   return self.send(200,result)
  if p.path=='/api/admin/commerce/health':
   u=self.user()
   if not u:return self.send(401,{'error':'Sign in required'})
   if u['role']!='admin':return self.send(403,{'error':'Admin access required'})
   with db() as c:result=assess_commerce_health(c)
   return self.send(200,result)
  if p.path=='/api/commerce/invoices':
   u=self.user()
   if not u:return self.send(401,{'error':'Sign in required'})
   with db() as c:
    expire_due(c)
    invoices=[dict(x) for x in c.execute('SELECT * FROM subscription_invoices WHERE user_id=? ORDER BY id DESC',(u['id'],))]
   return self.send(200,invoices)
  if p.path=='/api/commerce/payouts':
   u=self.user()
   if not u or u['role'] not in ('merchant','admin'):return self.send(403,{'error':'Merchant access required'})
   with db() as c:return self.send(200,[dict(x) for x in c.execute('SELECT * FROM merchant_payouts WHERE merchant_id=? ORDER BY id DESC',(u['id'],))])
  if p.path=='/api/integrations/status':
   return self.send(200,{'ai':bool(os.getenv('OPENAI_API_KEY')),'sslcommerz':bool(os.getenv('SSLCZ_STORE_ID') and os.getenv('SSLCZ_STORE_PASSWORD') and os.getenv('PUBLIC_BASE_URL')),'bkash':bk.configured(),'payouts':'manual reconciliation','subscriptions':'invoice tracking; recurring collection requires provider mandate'})
  return super().do_GET()
 def redirect(self,url):
  self.send_response(303);self.send_header('Location',url);self.send_header('Cache-Control','no-store');self.end_headers()
 def do_POST(self):
  # Commerce endpoints are intercepted before CatalogHandler.do_POST, so
  # enforce its cross-origin protection here too.
  if not commerce_browser_write_allowed(self.headers):
   return self.send(403,{'error':'Cross-origin request rejected'})
  p=urllib.parse.urlparse(self.path).path
  if p=='/api/admin/payout/review':
   u=self.user()
   if not u or u['role']!='admin':return self.send(403,{'error':'Admin access required'})
   b=self.body()
   try:
    payout_id=b.get('payout_id')
    if type(payout_id) is not int:raise ValueError('Invalid payout identifier')
    with db() as c:
     result=review_payout(c,payout_id,u['id'],b.get('status'),b.get('reference',''))
    return self.send(200,result)
   except LookupError:return self.send(404,{'error':'Payout not found'})
   except PermissionError:return self.send(403,{'error':'Self review forbidden'})
   except (ValueError,TypeError):return self.send(400,{'error':'Invalid payout review request'})
  if p=='/api/commerce/bkash/start':
   u=self.user()
   if not u:return self.send(401,{'error':'Sign in required'})
   b=self.body()
   try:oid=int(b.get('order_id'))
   except:return self.send(400,{'error':'Invalid order'})
   with db() as c:o=c.execute('SELECT * FROM orders WHERE id=? AND user_id=?',(oid,u['id'])).fetchone()
   if not o:return self.send(404,{'error':'Order not found'})
   if o['status']!='pending':return self.send(409,{'error':'Order not pending'})
   if not bk.configured():return self.send(503,{'error':'bKash merchant credentials not configured'})
   ref='LIBRA-'+str(oid)+'-'+secrets.token_hex(8)
   try:r=bk.create(ref,o['amount'])
   except Exception:return self.send(503,{'error':'bKash checkout unavailable; order remains pending'})
   with db() as c:c.execute('INSERT INTO bkash_attempts(order_id,user_id,reference,payment_id) VALUES(?,?,?,?)',(oid,u['id'],ref,r['payment_id']))
   return self.send(200,{'checkout_url':r['checkout_url']})
  if p=='/api/commerce/subscription/invoice':
   u=self.user()
   if not u:return self.send(401,{'error':'Sign in required'})
   body=self.body()
   if not isinstance(body,dict):return self.send(400,{'error':'Invalid request'})
   try:
    with db() as c:result=create_invoice(c,u['id'],body.get('plan'))
   except (ValueError,TypeError):return self.send(400,{'error':'Choose premium or student'})
   result['notice']='Invoice only; no access or recurring charge is activated without verified provider payment.'
   return self.send(200 if result['reused'] else 201,result)
  if p=='/api/commerce/subscription/cancel-invoice':
   u=self.user()
   if not u:return self.send(401,{'error':'Sign in required'})
   body=self.body()
   if not isinstance(body,dict):return self.send(400,{'error':'Invalid request'})
   try:
    with db() as c:result=cancel_invoice(c,u['id'],body.get('invoice_id'))
   except LookupError:return self.send(404,{'error':'Invoice not found'})
   except (ValueError,TypeError):return self.send(409,{'error':'Invoice cannot be cancelled'})
   return self.send(200,result)
  return super().do_POST()
if __name__=='__main__':
 from deployment_guard import require_development_server
 require_development_server()
 setup();port=int(os.getenv('PORT','8000'));print('LibraAI extended commerce http://127.0.0.1:'+str(port));ThreadingHTTPServer(('127.0.0.1',port),Commerce).serve_forever()
