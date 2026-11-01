"""Subscription invoice lifecycle; never grants entitlements or charges a card."""
import datetime

PRICES={'premium':'999.00','student':'399.00'}


def install(c):
    columns={row[1] for row in c.execute('PRAGMA table_info(subscription_invoices)')}
    if 'expires_at' not in columns:
        c.execute('ALTER TABLE subscription_invoices ADD COLUMN expires_at TEXT')
    # Existing invoices receive an explicit expiry; paid invoices remain unchanged.
    c.execute("UPDATE subscription_invoices SET expires_at=datetime(created,'+7 days') WHERE expires_at IS NULL AND status='unpaid'")
    expire_invoices(c)
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_subscription_active_invoice ON subscription_invoices(user_id,plan) WHERE status='unpaid'")
    c.commit()


def expire_invoices(c, now=None):
    """Expire unpaid invoices only; never touch paid or cancelled records."""
    now=now or datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    result=c.execute("UPDATE subscription_invoices SET status='expired' WHERE status='unpaid' AND expires_at IS NOT NULL AND expires_at<=?",(now,))
    return result.rowcount


def create_invoice(c,user_id,plan):
    if not isinstance(plan,str) or plan not in PRICES:
        raise ValueError('Unsupported plan')
    c.execute('BEGIN IMMEDIATE')
    try:
        expire_invoices(c)
        existing=c.execute("SELECT id,amount,currency,expires_at FROM subscription_invoices WHERE user_id=? AND plan=? AND status='unpaid'",(user_id,plan)).fetchone()
        if existing:
            result={'invoice_id':existing['id'],'amount':existing['amount'],'currency':existing['currency'],'expires_at':existing['expires_at'],'status':'unpaid','reused':True}
        else:
            c.execute("INSERT INTO subscription_invoices(user_id,plan,amount,expires_at) VALUES(?,?,?,datetime('now','+7 days'))",(user_id,plan,PRICES[plan]))
            row=c.execute('SELECT id,expires_at FROM subscription_invoices WHERE id=last_insert_rowid()').fetchone()
            result={'invoice_id':row['id'],'amount':PRICES[plan],'currency':'BDT','expires_at':row['expires_at'],'status':'unpaid','reused':False}
        c.commit()
        return result
    except Exception:
        c.rollback()
        raise


def cancel_invoice(c,user_id,invoice_id):
    if type(invoice_id) is not int or invoice_id<=0:raise ValueError('Invalid invoice')
    c.execute('BEGIN IMMEDIATE')
    try:
        expire_invoices(c)
        row=c.execute('SELECT user_id,status FROM subscription_invoices WHERE id=?',(invoice_id,)).fetchone()
        if row is None or row['user_id']!=user_id:raise LookupError('Invoice not found')
        if row['status']!='unpaid':raise ValueError('Only unpaid invoices may be cancelled')
        c.execute("UPDATE subscription_invoices SET status='cancelled' WHERE id=? AND status='unpaid'",(invoice_id,))
        c.commit()
        return {'invoice_id':invoice_id,'status':'cancelled'}
    except Exception:
        c.rollback()
        raise
