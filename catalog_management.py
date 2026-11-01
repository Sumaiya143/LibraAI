"""Strict, transactional catalog CSV import/export; no content licensing implied."""
import csv
import io
import math
import sqlite3

FIELDS = ('title','author','genre','year','format','price','stock','description','language','isbn','branch','shelf')
MAX_ROWS = 500

class CatalogValidationError(ValueError):
    pass

def validate_csv(data):
    if isinstance(data, bytes):
        try: data = data.decode('utf-8-sig')
        except UnicodeError as exc: raise CatalogValidationError('CSV must be UTF-8') from exc
    if len(data.encode('utf-8')) > 512_000:
        raise CatalogValidationError('CSV is too large (512 KB maximum)')
    try:
        reader = csv.DictReader(io.StringIO(data, newline=''), strict=True)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise CatalogValidationError('CSV headers are missing or duplicated')
        if set(reader.fieldnames) != set(FIELDS):
            raise CatalogValidationError('Expected headers: ' + ', '.join(FIELDS))
        result = []
        for index, row in enumerate(reader, start=2):
            if len(result) >= MAX_ROWS: raise CatalogValidationError('Maximum 500 books per upload')
            if None in row or any(v is None for v in row.values()):
                raise CatalogValidationError(f'Row {index}: malformed columns')
            clean = {key: row[key].strip() for key in FIELDS}
            for key, limit in [('title',200),('author',160),('genre',80),('format',100),('description',1500),('language',60),('isbn',32),('branch',100),('shelf',50)]:
                if not clean[key] or len(clean[key]) > limit:
                    raise CatalogValidationError(f'Row {index}: invalid {key}')
            try:
                year = int(clean['year']); stock = int(clean['stock']); price = float(clean['price'])
            except ValueError as exc: raise CatalogValidationError(f'Row {index}: invalid number') from exc
            if not 1450 <= year <= 2100 or not 0 <= stock <= 1000000 or not math.isfinite(price) or not 0 <= price <= 1000000:
                raise CatalogValidationError(f'Row {index}: number outside allowed range')
            clean.update(year=year, stock=stock, price=round(price,2))
            result.append(clean)
        if not result: raise CatalogValidationError('CSV contains no books')
        return result
    except csv.Error as exc:
        raise CatalogValidationError('Malformed CSV') from exc

def import_catalog(connection, data):
    """Validate entire file first; all-or-nothing insertion into the catalog."""
    books = validate_csv(data)
    with connection:
        connection.executemany('''INSERT INTO books
          (title,author,genre,year,format,price,stock,description,language,isbn,branch,shelf,rating,reads,sales)
          VALUES (:title,:author,:genre,:year,:format,:price,:stock,:description,:language,:isbn,:branch,:shelf,0,0,0)''',books)
    return len(books)

def export_catalog(connection):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(FIELDS)
    for row in connection.execute('SELECT '+','.join(FIELDS)+' FROM books ORDER BY id'):
        writer.writerow(tuple(("'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else value) for value in row))
    return stream.getvalue()
