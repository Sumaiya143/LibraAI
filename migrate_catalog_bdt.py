"""One-time explicit USD-to-BDT migration. Backup DB and approve exchange rate first."""
import argparse, sqlite3
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

def migrate(conn, rate):
    try:
        rate=Decimal(str(rate))
        if not rate.is_finite() or not Decimal('1') <= rate <= Decimal('1000'):
            raise ValueError('Rate must be a valid positive BDT per USD value')
    except (InvalidOperation, TypeError): raise ValueError('Invalid conversion rate')
    conn.execute('BEGIN IMMEDIATE')
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS commercial_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        row=conn.execute("SELECT value FROM commercial_metadata WHERE key='catalog_currency'").fetchone()
        if row: raise ValueError('Currency already recorded; refusing repeated migration')
        for table in ('books','resale'):
            for ident,price in conn.execute(f'SELECT id,price FROM {table}').fetchall():
                amount=Decimal(str(price))
                if not amount.is_finite() or amount<0: raise ValueError('Invalid legacy price')
                bdt=(amount*rate).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
                conn.execute(f'UPDATE {table} SET price=? WHERE id=?',(float(bdt),ident))
        # Existing unpaid orders and historical ledger values have unknown currency.
        # Fail rather than silently relabel or charge them.
        if conn.execute('SELECT 1 FROM orders LIMIT 1').fetchone():
            raise ValueError('Existing orders found; manually reconcile/migrate orders before conversion')
        conn.execute("INSERT INTO commercial_metadata VALUES('catalog_currency','BDT')")
        conn.execute("INSERT INTO commercial_metadata VALUES('conversion_rate_bdt_per_usd',?)",(str(rate),))
        conn.commit()
    except Exception:
        conn.rollback();raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database',required=True)
    p.add_argument('--approved-rate',required=True,help='Operator-approved BDT per USD; no rate is assumed')
    p.add_argument('--confirm-backup',action='store_true')
    a=p.parse_args()
    if not a.confirm_backup: p.error('Back up the database and pass --confirm-backup')
    with sqlite3.connect(a.database) as c: migrate(c,a.approved_rate)
    print('BDT catalog migration complete. Verify storefront prices before selling.')
