"""Read-only inventory readiness audit. Recorded references are NOT proof of rights."""
import argparse
import json
import sqlite3


def audit(conn):
    issues = []
    try:
        books = conn.execute('SELECT id,title,format,price,stock FROM books ORDER BY id').fetchall()
    except sqlite3.Error:
        return {'ready': False, 'books_checked': 0, 'issues': [{'code':'missing_catalog', 'book_id':None}]}
    for book in books:
        bid, title, fmt, price, stock = book
        if not title or not str(title).strip():
            issues.append({'code':'missing_title','book_id':bid})
        if price is None or not isinstance(price,(int,float)) or not (0 <= price < 100000000):
            issues.append({'code':'invalid_price','book_id':bid})
        if stock is None or not isinstance(stock,int) or stock < 0:
            issues.append({'code':'invalid_stock','book_id':bid})
        if fmt not in ('eBook','Print'):
            issues.append({'code':'unsupported_format','book_id':bid})
        if fmt == 'eBook':
            try:
                valid = conn.execute('''SELECT 1 FROM licensed_documents d
                    JOIN licensed_chunks c ON c.document_id=d.id
                    WHERE d.book_id=? AND d.access_policy='licensed'
                    AND LENGTH(TRIM(d.rights_holder))>0
                    AND LENGTH(TRIM(d.license_reference))>0
                    AND LENGTH(TRIM(c.content))>0 LIMIT 1''',(bid,)).fetchone()
            except sqlite3.Error:
                valid = None
            if not valid:
                issues.append({'code':'digital_content_or_rights_record_missing','book_id':bid})
    if not books:
        issues.append({'code':'empty_catalog','book_id':None})
    return {'ready':not issues,'books_checked':len(books),'issues':issues,
            'notice':'Rights records require independent publisher/license verification; this audit cannot establish legal permission.'}


def main():
    parser=argparse.ArgumentParser(description='Read-only LibraAI commercial catalog audit')
    parser.add_argument('--db',required=True)
    parser.add_argument('--require-ready',action='store_true')
    args=parser.parse_args()
    # SQLite URI mode=ro prevents accidental creation or mutation of production databases.
    from pathlib import Path
    db_path=Path(args.db).resolve()
    if not db_path.is_file():
        print(json.dumps({'ready':False,'error':'Database does not exist'}));return 2
    conn=sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True)
    try: report=audit(conn)
    finally: conn.close()
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 1 if args.require_ready and not report['ready'] else 0

if __name__=='__main__':
    raise SystemExit(main())
