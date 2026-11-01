"""Transactional sandbox commerce. Does not collect or settle real payments."""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from market_checkout_policy import validate_sale, SalePolicyError

class CheckoutError(ValueError):
    pass

def money(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS order_items (id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, book_id INTEGER NOT NULL, title_snapshot TEXT NOT NULL, unit_price_cents INTEGER NOT NULL, quantity INTEGER NOT NULL CHECK(quantity > 0), format TEXT NOT NULL, FOREIGN KEY(order_id) REFERENCES orders(id))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS order_amounts (order_id INTEGER PRIMARY KEY, total_cents INTEGER NOT NULL CHECK(total_cents >= 0), currency TEXT NOT NULL DEFAULT 'BDT', FOREIGN KEY(order_id) REFERENCES orders(id))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS checkout_requests (user_id INTEGER NOT NULL, request_key TEXT NOT NULL, order_id INTEGER NOT NULL, PRIMARY KEY(user_id,request_key))''')
    columns={r[1] for r in conn.execute("PRAGMA table_info(order_items)")}
    if "line_total_cents" not in columns:
        conn.execute("ALTER TABLE order_items ADD COLUMN line_total_cents INTEGER")
    conn.commit()

def place_sandbox_order(conn, user_id, request_key, coupon='', address=''):
    """Atomic, idempotent, stock-aware order reservation; never represents payment as settled."""
    if type(user_id) is not int or user_id <= 0:
        raise CheckoutError('Invalid account identifier')
    if not isinstance(request_key, str) or not 8 <= len(request_key) <= 128:
        raise CheckoutError('Invalid checkout request identifier')
    if not isinstance(address, str) or len(address) > 500:
        raise CheckoutError('Invalid delivery address')
    if not isinstance(coupon, str) or len(coupon) > 64:
        raise CheckoutError('Invalid coupon')
    conn.execute('BEGIN IMMEDIATE')
    try:
        previous=conn.execute('SELECT order_id FROM checkout_requests WHERE user_id=? AND request_key=?',(user_id,request_key)).fetchone()
        if previous:
            conn.commit()
            return previous[0], False
        rows=conn.execute('''SELECT c.book_id,c.qty,c.format,b.title,b.price,b.stock FROM cart c JOIN books b ON b.id=c.book_id WHERE c.user_id=? ORDER BY c.id''',(user_id,)).fetchall()
        if not rows:
            raise CheckoutError('Cart is empty')
        try:
            validate_sale(conn, rows, address)
        except SalePolicyError as exc:
            raise CheckoutError(str(exc)) from exc
        total_cents=0
        line_totals=[]
        print_demand={}
        for r in rows:
            bid, qty, fmt, title, price, stock = r
            if not isinstance(qty,int) or qty <= 0 or qty > 100:
                raise CheckoutError('Invalid cart quantity')
            if fmt not in ('Print', 'eBook'):
                raise CheckoutError('Unsupported cart format')
            if fmt == 'Print':
                print_demand[bid] = print_demand.get(bid, 0) + qty
                if stock is None or stock < print_demand[bid]:
                    raise CheckoutError(f'Insufficient print stock for {title}')
            try:
                price_decimal = Decimal(str(price))
                if not price_decimal.is_finite() or price_decimal < 0 or price_decimal.as_tuple().exponent < -2:
                    raise CheckoutError('Invalid catalog price')
                unit_cents = int(price_decimal * 100)
                if unit_cents > 9223372036854775807 // qty:
                    raise CheckoutError('Catalog amount exceeds storage range')
            except (InvalidOperation, ValueError, OverflowError, TypeError) as exc:
                raise CheckoutError('Invalid catalog price') from exc
            line_total=unit_cents*qty
            line_totals.append(line_total)
            total_cents += line_total
            if total_cents > 9223372036854775807:
                raise CheckoutError('Order amount exceeds storage range')
        if coupon.strip().upper() == 'LIBRA10' and __import__('os').environ.get('LIBRAAI_ENV') != 'production':
            total_cents=int((Decimal(total_cents)*Decimal('.90')).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        # Allocate the actual charged total across lines, preserving every cent.
        gross=sum(line_totals)
        if gross:
            allocated=[v*total_cents//gross for v in line_totals]
            remainder=total_cents-sum(allocated)
            priorities=sorted(range(len(rows)),key=lambda i:(-(line_totals[i]*total_cents%gross),i))
            for i in priorities[:remainder]: allocated[i]+=1
        else:
            allocated=[0]*len(rows)
        now=datetime.now(timezone.utc).isoformat()
        cur=conn.execute('INSERT INTO orders(user_id,total,status,address,created) VALUES(?,?,?,?,?)',(user_id,float(Decimal(total_cents)/100),'Awaiting payment — sandbox only',address,now))
        order_id=cur.lastrowid
        conn.execute("INSERT INTO order_amounts(order_id,total_cents,currency) VALUES(?,?,?)", (order_id,total_cents,"BDT"))
        for (bid,qty,fmt,title,price,stock),line_paid in zip(rows,allocated):
            conn.execute('INSERT INTO order_items(order_id,book_id,title_snapshot,unit_price_cents,quantity,format,line_total_cents) VALUES(?,?,?,?,?,?,?)',(order_id,bid,title,int(money(price)*100),qty,fmt,line_paid))
            if fmt == 'Print':
                updated=conn.execute('UPDATE books SET stock=stock-? WHERE id=? AND stock>=?', (qty,bid,qty))
                if updated.rowcount != 1:
                    raise CheckoutError('Print stock changed; retry checkout')
        conn.execute('INSERT INTO checkout_requests(user_id,request_key,order_id) VALUES(?,?,?)',(user_id,request_key,order_id))
        conn.execute('DELETE FROM cart WHERE user_id=?',(user_id,))
        conn.commit()
        return order_id, True
    except Exception:
        conn.rollback()
        raise
