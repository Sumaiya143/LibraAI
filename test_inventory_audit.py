import sqlite3
import unittest
from inventory_audit_engine import setup, record_count

class InventoryAuditTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.execute('CREATE TABLE books(id INTEGER PRIMARY KEY, stock INTEGER)')
        self.c.execute('INSERT INTO books VALUES(1, 10)')
        setup(self.c)
    def tearDown(self): self.c.close()
    def test_record_without_changing_stock(self):
        x=record_count(self.c, book_id=1, counted=8, actor_id=1)
        self.assertEqual(x['difference'],-2)
        self.assertEqual(self.c.execute('SELECT stock FROM books').fetchone()[0],10)
    def test_explicit_reconciliation(self):
        record_count(self.c,book_id=1,counted=8,actor_id=1,apply=True)
        self.assertEqual(self.c.execute('SELECT stock FROM books').fetchone()[0],8)
    def test_invalid_count_has_no_side_effect(self):
        with self.assertRaises(ValueError): record_count(self.c,book_id=1,counted=-1,actor_id=1)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM stock_audits').fetchone()[0],0)
    def test_missing_book_rolls_back(self):
        with self.assertRaises(ValueError): record_count(self.c,book_id=99,counted=1,actor_id=1)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM stock_audits').fetchone()[0],0)
if __name__=='__main__': unittest.main()
