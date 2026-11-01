import io
import sqlite3
import unittest
from catalog_management import FIELDS, CatalogValidationError, validate_csv, import_catalog, export_catalog

HEADER=','.join(FIELDS)
ROW='Original Title,Writer,Fiction,2024,eBook,9.99,5,Sample description,English,1234567890,Central,A-1'

class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute('''CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT,author TEXT,genre TEXT,year INTEGER,format TEXT,price REAL,stock INTEGER,description TEXT,language TEXT,isbn TEXT,branch TEXT,shelf TEXT,rating REAL,reads INTEGER,sales INTEGER)''')
    def tearDown(self): self.db.close()
    def test_valid_import(self):
        self.assertEqual(import_catalog(self.db,HEADER+'\n'+ROW),1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM books').fetchone()[0],1)
    def test_export_round_trip(self):
        import_catalog(self.db,HEADER+'\n'+ROW)
        self.assertEqual(validate_csv(export_catalog(self.db))[0]['title'],'Original Title')
    def test_bad_number_rejected(self):
        with self.assertRaises(CatalogValidationError): validate_csv(HEADER+'\n'+ROW.replace('9.99','NaN'))
    def test_bad_row_is_atomic(self):
        with self.assertRaises(CatalogValidationError): import_catalog(self.db,HEADER+'\n'+ROW+'\n'+ROW.replace('9.99','-1'))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM books').fetchone()[0],0)
    def test_malformed_headers(self):
        with self.assertRaises(CatalogValidationError): validate_csv('title,author\na,b')
    def test_row_limit(self):
        with self.assertRaises(CatalogValidationError): validate_csv(HEADER+'\n'+('\n'.join([ROW]*501)))
    def test_csv_injection_export(self):
        # Exported CSV must not execute spreadsheet formulas when opened in Excel.
        import_catalog(self.db,HEADER+'\n'+ROW.replace('Original Title','=HYPERLINK("http://example.test")'))
        exported=export_catalog(self.db)
        self.assertTrue(next(__import__('csv').DictReader(io.StringIO(exported)))['title'].startswith("'=HYPERLINK"))

if __name__=='__main__': unittest.main()
