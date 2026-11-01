import sqlite3
import unittest
from inventory_launch_audit import audit

class InventoryLaunchAuditTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        self.conn.executescript('''CREATE TABLE books(id INTEGER PRIMARY KEY,title TEXT,format TEXT,price REAL,stock INTEGER);
        CREATE TABLE licensed_documents(id INTEGER PRIMARY KEY,book_id INTEGER,access_policy TEXT,rights_holder TEXT,license_reference TEXT);
        CREATE TABLE licensed_chunks(document_id INTEGER,content TEXT);''')
    def tearDown(self): self.conn.close()
    def test_empty_catalog_blocked(self):
        self.assertIn('empty_catalog',[x['code'] for x in audit(self.conn)['issues']])
    def test_print_valid(self):
        self.conn.execute("INSERT INTO books VALUES(1,'Print','Print',100,2)")
        self.assertTrue(audit(self.conn)['ready'])
    def test_ebook_without_license_blocked(self):
        self.conn.execute("INSERT INTO books VALUES(1,'Digital','eBook',100,2)")
        self.assertFalse(audit(self.conn)['ready'])
    def test_ebook_with_licensed_content_record(self):
        self.conn.execute("INSERT INTO books VALUES(1,'Digital','eBook',100,2)")
        self.conn.execute("INSERT INTO licensed_documents VALUES(1,1,'licensed','Publisher','Agreement-1')")
        self.conn.execute("INSERT INTO licensed_chunks VALUES(1,'Sample content')")
        self.assertTrue(audit(self.conn)['ready'])
    def test_invalid_stock_price_and_format(self):
        self.conn.execute("INSERT INTO books VALUES(1,'Unknown','audio',-1,-3)")
        self.assertEqual(len(audit(self.conn)['issues']),3)
    def test_missing_license_tables_fail_closed(self):
        self.conn.execute('DROP TABLE licensed_chunks')
        self.conn.execute("INSERT INTO books VALUES(1,'Digital','eBook',100,2)")
        self.assertFalse(audit(self.conn)['ready'])

if __name__=='__main__': unittest.main()
