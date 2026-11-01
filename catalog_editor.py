"""Validated, audited catalog editing; metadata only, never content entitlements."""
from decimal import Decimal, InvalidOperation

class CatalogEditError(ValueError):
    pass

def clean_book(form):
    fields = {}
    for key, limit, required in [('title',180,True),('author',140,True),('genre',80,True),('description',2000,False),('language',60,False),('isbn',32,False),('branch',80,False),('shelf',40,False),('format',100,True)]:
        value = str(form.get(key, '')).strip()
        if len(value)>limit or (required and not value) or any(ord(ch)<32 for ch in value):
            raise CatalogEditError('Invalid '+key)
        fields[key]=value
    for key, low, high in [('stock',0,1000000),('year',1450,2200)]:
        raw=str(form.get(key,'')).strip()
        if not raw.isascii() or not raw.isdecimal():
            raise CatalogEditError('Invalid '+key)
        value=int(raw)
        if not low<=value<=high:
            raise CatalogEditError('Invalid '+key)
        fields[key]=value
    try:
        price=Decimal(str(form.get('price','')))
        if not price.is_finite() or price<0 or price>Decimal('100000') or price.as_tuple().exponent < -2:
            raise CatalogEditError('Invalid price')
    except (InvalidOperation, ValueError, TypeError):
        raise CatalogEditError('Invalid price') from None
    fields['price']=float(price)
    return fields

def save_book(conn, values, actor_id, book_id=None):
    """Only call after server-side administrator authorization."""
    keys=list(values)
    if book_id is None:
        cursor=conn.execute('INSERT INTO books ('+','.join(keys)+',rating,reads,sales) VALUES ('+','.join('?' for _ in keys)+',0,0,0)',tuple(values.values()))
        book_id=cursor.lastrowid
        action='catalog.create'
    else:
        cursor=conn.execute('UPDATE books SET '+','.join(k+'=?' for k in keys)+' WHERE id=?',(*values.values(),book_id))
        if cursor.rowcount != 1:
            raise CatalogEditError('Book not found')
        action='catalog.update'
    conn.execute("INSERT INTO audit(user_id,action,created) VALUES(?,?,datetime('now'))",(actor_id,action+' #'+str(book_id)))
    return book_id
