"""Authenticated seller product, inventory, sales and earnings workspace."""
from flask import Blueprint, jsonify, request
from decimal import Decimal, InvalidOperation
import json, os, re, sqlite3

ALLOWED_TYPES = {'book','ebook','stationery','audiobook','manga','comic','other'}


def install_seller_workspace(app, db, current_user):
    bp = Blueprint('seller_workspace', __name__)

    def seller():
        user = current_user()
        if not user:
            return None, (jsonify({'error':'Sign in required','code':'auth_required'}),401)
        if str(user['role'] or '').lower() not in ('merchant','creator'):
            return None, (jsonify({'error':'Seller account required','code':'seller_required'}),403)
        return user, None

    def commission_rate():
        raw=os.getenv('LIBRAAI_PLATFORM_COMMISSION_RATE')
        if raw is None or not raw.strip(): return None
        try: return max(0.0,min(50.0,float(raw)))
        except ValueError: return None

    def setup(conn):
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS seller_products (
          id INTEGER PRIMARY KEY,
          seller_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          book_id INTEGER REFERENCES books(id) ON DELETE SET NULL,
          product_type TEXT NOT NULL,
          title TEXT NOT NULL,
          subtitle TEXT NOT NULL DEFAULT '',
          description TEXT NOT NULL DEFAULT '',
          details_json TEXT NOT NULL DEFAULT '{}',
          tags_json TEXT NOT NULL DEFAULT '[]',
          hashtags_json TEXT NOT NULL DEFAULT '[]',
          image_url TEXT NOT NULL DEFAULT '',
          price REAL NOT NULL CHECK(price>=0),
          discount_percent REAL NOT NULL DEFAULT 0 CHECK(discount_percent BETWEEN 0 AND 95),
          stock INTEGER NOT NULL DEFAULT 0 CHECK(stock>=0),
          sku TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'pending_review',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_seller_products_owner ON seller_products(seller_id,created_at DESC);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_seller_products_sku ON seller_products(seller_id,sku) WHERE sku != ''; 
        CREATE TABLE IF NOT EXISTS seller_payout_requests (
          id INTEGER PRIMARY KEY, seller_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          amount REAL NOT NULL CHECK(amount>0), status TEXT NOT NULL DEFAULT 'requested',
          reference TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        ''')

    def clean(data):
        if not isinstance(data,dict): raise ValueError('Product information must be an object.')
        title = str(data.get('title','')).strip()
        ptype = str(data.get('product_type','book')).strip().lower()
        description = str(data.get('description','')).strip()
        subtitle = str(data.get('subtitle','')).strip()
        image_url = str(data.get('image_url','')).strip()
        sku = str(data.get('sku','')).strip()[:80]
        if not 2 <= len(title) <= 180: raise ValueError('Product title must contain 2–180 characters.')
        if ptype not in ALLOWED_TYPES: raise ValueError('Choose a supported product type.')
        if len(description)>5000 or len(subtitle)>240: raise ValueError('Description or subtitle is too long.')
        if image_url and not image_url.startswith('https://'): raise ValueError('Product image must use a secure HTTPS URL.')
        try:
            price=Decimal(str(data.get('price',''))); discount=Decimal(str(data.get('discount_percent',0)))
            stock=int(data.get('stock',0))
            if not price.is_finite() or price<0 or price>Decimal('10000000') or price.as_tuple().exponent < -2: raise ValueError()
            if not discount.is_finite() or discount<0 or discount>95: raise ValueError()
            if stock<0 or stock>10000000: raise ValueError()
        except (InvalidOperation,ValueError,TypeError): raise ValueError('Enter a valid price, discount (0–95%) and stock quantity.')
        tags=data.get('tags',[]); hashtags=data.get('hashtags',[]); details=data.get('details',{})
        if isinstance(tags,str): tags=[x.strip() for x in tags.split(',') if x.strip()]
        if isinstance(hashtags,str): hashtags=[x.strip().lstrip('#') for x in hashtags.split(',') if x.strip()]
        if not isinstance(tags,list) or not isinstance(hashtags,list) or not isinstance(details,dict): raise ValueError('Tags, hashtags or product details are invalid.')
        tags=[str(x).strip()[:40] for x in tags[:30] if str(x).strip()]
        hashtags=[re.sub(r'[^\w-]','',str(x).lstrip('#'))[:40] for x in hashtags[:30] if str(x).strip()]
        if len(json.dumps(details,ensure_ascii=False))>12000: raise ValueError('Product details are too large.')
        return {'title':title,'product_type':ptype,'subtitle':subtitle,'description':description,'image_url':image_url,
                'price':float(price),'discount_percent':float(discount),'stock':stock,'sku':sku,
                'tags_json':json.dumps(tags,ensure_ascii=False),'hashtags_json':json.dumps(hashtags,ensure_ascii=False),
                'details_json':json.dumps(details,ensure_ascii=False)}

    def product_dict(row):
        item=dict(row)
        for key,out in [('tags_json','tags'),('hashtags_json','hashtags'),('details_json','details')]:
            try:item[out]=json.loads(item.pop(key) or ('{}' if key=='details_json' else '[]'))
            except Exception:item[out]={} if key=='details_json' else []
        item['sale_price']=round(float(item['price'])*(1-float(item['discount_percent'])/100),2)
        if item.get('sale_enabled') is not None and int(item['sale_enabled'])==1:item['status']='active'
        item.pop('sale_enabled',None)
        return item

    @bp.get('/api/seller/products')
    def products():
        user,error=seller()
        if error:return error
        with db() as conn:
            setup(conn)
            rows=conn.execute('SELECT sp.*,COALESCE(cp.sale_enabled,0) sale_enabled FROM seller_products sp LEFT JOIN catalog_products cp ON cp.book_id=sp.book_id WHERE sp.seller_id=? ORDER BY sp.id DESC',(user['id'],)).fetchall()
        return jsonify([product_dict(r) for r in rows])

    @bp.post('/api/seller/products')
    def create_product():
        user,error=seller()
        if error:return error
        try: values=clean(request.get_json(silent=True) or {})
        except ValueError as exc:return jsonify({'error':str(exc)}),400
        with db() as conn:
            setup(conn)
            if values['sku'] and conn.execute('SELECT 1 FROM seller_products WHERE seller_id=? AND sku=?',(user['id'],values['sku'])).fetchone():return jsonify({'error':'This SKU already exists in your store.'}),409
            # Keep a catalog-facing record so the existing discovery/search layer can index the listing.
            cur=conn.execute('INSERT INTO books(title,author,genre,rating,reads,sales,year,format,price,stock,description,language,isbn,branch,shelf) VALUES(?,?,?,0,0,0,2026,?,?,?,?,?,?,?,?)',
                (values['title'],user['name'] or 'LibraAI Seller',values['product_type'].title(),values['product_type'],round(values['price']*(1-values['discount_percent']/100),2),values['stock'],values['description'],'English',values['sku'],'Marketplace','Seller'))
            book_id=cur.lastrowid
            conn.execute('INSERT OR IGNORE INTO catalog_products(book_id,product_type,sale_enabled,digital_available,inventory_quantity,access_type) VALUES(?,?,0,?,?,?)',
                (book_id,values['product_type'],1 if values['product_type'] in ('ebook','audiobook') else 0,values['stock'],'purchase'))
            keys=list(values)+['seller_id','book_id']
            vals=list(values.values())+[user['id'],book_id]
            cur=conn.execute('INSERT INTO seller_products('+','.join(keys)+') VALUES('+','.join('?' for _ in keys)+')',vals)
            pid=cur.lastrowid
        return jsonify({'ok':True,'id':pid,'book_id':book_id,'status':'pending_review','message':'Product submitted for catalog review.'}),201

    @bp.put('/api/seller/products/<int:product_id>')
    def update_product(product_id):
        user,error=seller()
        if error:return error
        try:values=clean(request.get_json(silent=True) or {})
        except ValueError as exc:return jsonify({'error':str(exc)}),400
        with db() as conn:
            setup(conn)
            row=conn.execute('SELECT book_id FROM seller_products WHERE id=? AND seller_id=?',(product_id,user['id'])).fetchone()
            if not row:return jsonify({'error':'Product not found.'}),404
            if values['sku'] and conn.execute('SELECT 1 FROM seller_products WHERE seller_id=? AND sku=? AND id!=?',(user['id'],values['sku'],product_id)).fetchone():return jsonify({'error':'This SKU already exists in your store.'}),409
            fields=list(values)
            conn.execute('UPDATE seller_products SET '+','.join(k+'=?' for k in fields)+",status='pending_review',updated_at=CURRENT_TIMESTAMP WHERE id=? AND seller_id=?",[values[k] for k in fields]+[product_id,user['id']])
            if row['book_id']:
                conn.execute('UPDATE books SET title=?,genre=?,format=?,price=?,stock=?,description=? WHERE id=?',(values['title'],values['product_type'].title(),values['product_type'],round(values['price']*(1-values['discount_percent']/100),2),values['stock'],values['description'],row['book_id']))
                conn.execute('UPDATE catalog_products SET sale_enabled=0,inventory_quantity=?,updated_at=CURRENT_TIMESTAMP WHERE book_id=?',(values['stock'],row['book_id']))
        return jsonify({'ok':True,'id':product_id,'status':'pending_review'})

    @bp.get('/api/seller/overview')
    def overview():
        user,error=seller()
        if error:return error
        with db() as conn:
            setup(conn)
            products_count=conn.execute('SELECT COUNT(*) FROM seller_products WHERE seller_id=?',(user['id'],)).fetchone()[0]
            stock=conn.execute('SELECT COALESCE(SUM(stock),0) FROM seller_products WHERE seller_id=?',(user['id'],)).fetchone()[0]
            # Attribute marketplace book orders only when their book_id belongs to this seller.
            cols={r['name'] for r in conn.execute('PRAGMA table_info(order_items)').fetchall()}
            if cols and {'order_id','book_id','quantity','unit_price_cents'} <= cols:
                total_expr='COALESCE(oi.line_total_cents,oi.unit_price_cents*oi.quantity)' if 'line_total_cents' in cols else 'oi.unit_price_cents*oi.quantity'
                rows=conn.execute(f'''SELECT o.id order_id,o.status,o.created,sp.id product_id,sp.title,oi.quantity,
                    oi.unit_price_cents/100.0 unit_price,{total_expr}/100.0 gross
                    FROM order_items oi JOIN orders o ON o.id=oi.order_id
                    JOIN seller_products sp ON sp.book_id=oi.book_id AND sp.seller_id=?
                    WHERE lower(COALESCE(o.status,'')) NOT IN ('cancelled','failed') ORDER BY o.id DESC LIMIT 500''',(user['id'],)).fetchall()
                sales=[dict(r) for r in rows]
            else:sales=[]
            status_orders={'delivered':set(),'pending':set(),'returned':set(),'processing':set()}
            for s in sales:
                st=str(s['status'] or '').lower(); oid=int(s['order_id'])
                if st in ('delivered','completed','fulfilled'):status_orders['delivered'].add(oid)
                elif 'return' in st or 'refund' in st:status_orders['returned'].add(oid)
                elif st in ('pending','awaiting_payment','unpaid'):status_orders['pending'].add(oid)
                else:status_orders['processing'].add(oid)
            statuses={'total':len({int(s['order_id']) for s in sales}),**{k:len(v) for k,v in status_orders.items()}}
            fee_rate=commission_rate()
            paid=[s for s in sales if str(s['status'] or '').lower() in ('delivered','completed','fulfilled')]
            gross=sum(float(s['gross'] or 0) for s in paid); fee=round(gross*fee_rate/100,2) if fee_rate is not None else None; net=round(gross-fee,2) if fee is not None else None
            top=conn.execute('SELECT sp.id,sp.title,sp.product_type,COALESCE(SUM(CASE WHEN o.id IS NOT NULL THEN oi.quantity ELSE 0 END),0) units,COALESCE(SUM(CASE WHEN o.id IS NOT NULL THEN '+total_expr+' ELSE 0 END),0)/100.0 gross FROM seller_products sp LEFT JOIN order_items oi ON oi.book_id=sp.book_id LEFT JOIN orders o ON o.id=oi.order_id AND lower(COALESCE(o.status,\'\')) IN (\'delivered\',\'completed\',\'fulfilled\') WHERE sp.seller_id=? GROUP BY sp.id ORDER BY units DESC,gross DESC LIMIT 5',(user['id'],)).fetchall() if sales else []
            payouts=[dict(r) for r in conn.execute('SELECT id,amount,status,reference,created_at FROM seller_payout_requests WHERE seller_id=? ORDER BY id DESC LIMIT 30',(user['id'],))]
        return jsonify({'product_count':products_count,'stock_units':stock,'orders':sales,'order_status':statuses,'gross_earnings':round(gross,2),'platform_fee':fee,'platform_fee_rate':fee_rate,'net_earnings':net,'top_products':[dict(r) for r in top],'payouts':payouts,'commission_note':'Platform commission is estimated from LIBRAAI_PLATFORM_COMMISSION_RATE. Configure the rate before displaying net earnings or requesting payouts.'})

    @bp.post('/api/seller/payout-requests')
    def payout_request():
        user,error=seller()
        if error:return error
        data=request.get_json(silent=True) or {}
        try:amount=Decimal(str(data.get('amount','')))
        except Exception:return jsonify({'error':'Enter a valid payout amount.'}),400
        if not amount.is_finite() or amount<=0 or amount>Decimal('10000000'):return jsonify({'error':'Payout amount is outside the allowed range.'}),400
        with db() as conn:
            setup(conn)
            # Prevent requests exceeding earned balance after earlier unsettled/paid payouts.
            cols={r['name'] for r in conn.execute('PRAGMA table_info(order_items)').fetchall()}
            if cols and {'order_id','book_id','quantity','unit_price_cents'} <= cols:
                gross_expr='COALESCE(oi.line_total_cents,oi.unit_price_cents*oi.quantity)' if 'line_total_cents' in cols else 'oi.unit_price_cents*oi.quantity'
                gross=conn.execute("SELECT COALESCE(SUM("+gross_expr+"),0)/100.0 FROM order_items oi JOIN orders o ON o.id=oi.order_id JOIN seller_products sp ON sp.book_id=oi.book_id WHERE sp.seller_id=? AND lower(COALESCE(o.status,'')) IN ('delivered','completed','fulfilled')",(user['id'],)).fetchone()[0]
            else:gross=0
            rate=commission_rate()
            if rate is None:return jsonify({'error':'Platform commission rate is not configured. Contact the platform administrator before requesting a payout.'}),503
            net=float(gross)*(1-rate/100)
            reserved=conn.execute("SELECT COALESCE(SUM(amount),0) FROM seller_payout_requests WHERE seller_id=? AND status IN ('requested','approved','processing','paid')",(user['id'],)).fetchone()[0]
            available=max(0.0,net-float(reserved or 0))
            if float(amount)>available+0.0001:return jsonify({'error':'Requested amount exceeds your available seller balance.'}),400
            cur=conn.execute("INSERT INTO seller_payout_requests(seller_id,amount,status,reference) VALUES(?,?,'requested',?)",(user['id'],float(amount),str(data.get('reference',''))[:120]))
        return jsonify({'ok':True,'id':cur.lastrowid,'status':'requested'}),201

    app.register_blueprint(bp)
