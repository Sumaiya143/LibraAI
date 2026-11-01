import sqlite3
import unittest
from account_export_core import export_account_data

class ExportTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        self.conn.executescript('''CREATE TABLE users(id INTEGER,name TEXT,email TEXT,password TEXT,role TEXT,plan TEXT);
        CREATE TABLE annotations(id INTEGER,user_id INTEGER,content TEXT);
        CREATE TABLE orders(id INTEGER,user_id INTEGER,total REAL);
        INSERT INTO users VALUES(1,'A','a@example.com','secret-hash','reader','Free');
        INSERT INTO users VALUES(2,'B','b@example.com','another-hash','reader','Free');
        INSERT INTO annotations VALUES(1,1,'private a');
        INSERT INTO annotations VALUES(2,2,'private b');
        INSERT INTO orders VALUES(1,1,5.0);
        INSERT INTO orders VALUES(2,2,100.0);''')
    def tearDown(self): self.conn.close()
    def test_scope(self):
        data=export_account_data(self.conn,1)
        self.assertEqual(len(data['records']['annotations']),1)
        self.assertEqual(data['records']['annotations'][0]['content'],'private a')
        self.assertEqual(len(data['records']['orders']),1)
    def test_no_password(self):
        self.assertNotIn('password',str(export_account_data(self.conn,1)))
        self.assertNotIn('secret-hash',str(export_account_data(self.conn,1)))
    def test_missing_user(self):
        with self.assertRaises(LookupError): export_account_data(self.conn,99)
    def test_missing_optional_tables(self):
        self.assertNotIn('flashcards',export_account_data(self.conn,1)['records'])
if __name__=='__main__': unittest.main()
