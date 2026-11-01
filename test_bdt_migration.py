import sqlite3,unittest,tempfile
from pathlib import Path
from migrate_catalog_bdt import migrate
from commercial_readiness import inspect

class CurrencyTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:')
  self.c.executescript('CREATE TABLE books(id INTEGER PRIMARY KEY,price REAL); CREATE TABLE resale(id INTEGER PRIMARY KEY,price REAL); CREATE TABLE orders(id INTEGER PRIMARY KEY); INSERT INTO books VALUES(1,10); INSERT INTO resale VALUES(1,2);')
 def tearDown(self): self.c.close()
 def test_conversion(self):
  migrate(self.c,'120')
  self.assertEqual(self.c.execute('SELECT price FROM books').fetchone()[0],1200)
  self.assertEqual(self.c.execute('SELECT price FROM resale').fetchone()[0],240)
 def test_idempotency(self):
  migrate(self.c,'120')
  with self.assertRaises(ValueError): migrate(self.c,'120')
 def test_refuse_existing_orders(self):
  self.c.execute('INSERT INTO orders VALUES(1)');self.c.commit()
  with self.assertRaises(ValueError): migrate(self.c,'120')
  self.assertEqual(self.c.execute('SELECT price FROM books').fetchone()[0],10)
 def test_invalid_rate(self):
  for rate in ['NaN','-5','0','1001','oops']:
   with self.assertRaises(ValueError): migrate(self.c,rate)
 def test_readiness_requires_database_marker(self):
  with tempfile.TemporaryDirectory() as tmp:
   env={'LIBRAAI_DB_PATH':str(Path(tmp)/'missing.db')}
   self.assertTrue(any('Database missing' in x for x in inspect(env,Path(tmp))['issues']))
if __name__=='__main__':unittest.main()
