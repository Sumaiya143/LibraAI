import unittest, sqlite3
from catalog_editor import clean_book, save_book, CatalogEditError

class CatalogEditorTests(unittest.TestCase):
    def setUp(self):
        self.form=dict(title='New book',author='Author',genre='Science',format='Print',price='19.99',stock='5',year='2026',isbn='',description='Test')
    def test_valid(self):
        self.assertEqual(clean_book(self.form)['price'],19.99)
    def test_invalid_prices(self):
        for price in ['NaN','Infinity','-1','1.001','100001','x']:
            with self.subTest(price=price), self.assertRaises(CatalogEditError): clean_book(dict(self.form,price=price))
    def test_stock(self):
        for stock in ['-1','1.5','1000001','abc']:
            with self.subTest(stock=stock), self.assertRaises(CatalogEditError): clean_book(dict(self.form,stock=stock))
    def test_title_and_control_chars(self):
        for title in ['', 'a'*181,'Bad\nTitle']:
            with self.subTest(title=title), self.assertRaises(CatalogEditError): clean_book(dict(self.form,title=title))
    def test_insert_update_and_audit(self):
        conn=sqlite3.connect(':memory:')
        conn.executescript('CREATE TABLE books(id INTEGER PRIMARY KEY,title TEXT,author TEXT,genre TEXT,description TEXT,language TEXT,isbn TEXT,branch TEXT,shelf TEXT,format TEXT,stock INTEGER,year INTEGER,price REAL,rating REAL,reads INTEGER,sales INTEGER);CREATE TABLE audit(user_id INTEGER,action TEXT,created TEXT);')
        values=clean_book(self.form)
        with conn: bid=save_book(conn,values,7)
        self.assertEqual(conn.execute('SELECT stock FROM books').fetchone()[0],5)
        with conn: save_book(conn,dict(values,stock=9),7,bid)
        self.assertEqual(conn.execute('SELECT stock FROM books').fetchone()[0],9)
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM audit').fetchone()[0],2)
        with self.assertRaises(CatalogEditError): save_book(conn,values,7,999)
        conn.close()
if __name__=='__main__': unittest.main()
