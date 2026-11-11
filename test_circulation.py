import sqlite3, unittest, tempfile, os
from datetime import datetime, timezone, timedelta
from circulation import setup, borrow_book, update_loan, CirculationError

class CirculationTests(unittest.TestCase):
    def setUp(self):
        fd,self.path=tempfile.mkstemp(suffix='.sqlite'); os.close(fd)
        self.conn=sqlite3.connect(self.path)
        self.conn.row_factory=sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.executescript('''CREATE TABLE books(id INTEGER PRIMARY KEY,title TEXT,branch TEXT,stock INTEGER);
          CREATE TABLE loans(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,status TEXT,due TEXT,branch TEXT,created TEXT);
          INSERT INTO books VALUES(1,'Book One','Central',2),(2,'Book Two','Central',1),(3,'Book Three','North',0),(4,'Book Four','Central',1),(5,'Book Five','Central',1),(6,'Book Six','Central',1),(7,'Book Seven','Central',1);''')
        self.conn.close()
        def factory():
            c=sqlite3.connect(self.path); c.row_factory=sqlite3.Row; return c
        setup(factory)
        self.conn=sqlite3.connect(self.path); self.conn.row_factory=sqlite3.Row
    def tearDown(self):
        self.conn.close(); os.unlink(self.path)
    def test_borrow_decrements_and_return_restores_inventory(self):
        loan=borrow_book(self.conn,10,1,datetime(2026,11,1,tzinfo=timezone.utc))
        self.assertEqual(loan['due'],'2026-11-15')
        self.assertEqual(self.conn.execute('SELECT available_copies FROM library_inventory WHERE book_id=1').fetchone()[0],1)
        update_loan(self.conn,loan['loan_id'],'return',10,datetime(2026,11,2,tzinfo=timezone.utc))
        self.assertEqual(self.conn.execute('SELECT available_copies FROM library_inventory WHERE book_id=1').fetchone()[0],2)
    def test_unavailable_copy_rejected(self):
        with self.assertRaises(CirculationError) as ctx: borrow_book(self.conn,10,3)
        self.assertEqual(ctx.exception.code,'unavailable')
    def test_duplicate_active_loan_rejected(self):
        borrow_book(self.conn,10,1)
        with self.assertRaises(CirculationError) as ctx: borrow_book(self.conn,10,1)
        self.assertEqual(ctx.exception.code,'already_borrowed')
    def test_renew_once_only(self):
        loan=borrow_book(self.conn,10,1,datetime(2026,11,1,tzinfo=timezone.utc))
        first=update_loan(self.conn,loan['loan_id'],'renew',10,datetime(2026,11,2,tzinfo=timezone.utc))
        self.assertEqual(first['due'],'2026-11-29')
        with self.assertRaises(CirculationError) as ctx: update_loan(self.conn,loan['loan_id'],'renew',10,datetime(2026,11,3,tzinfo=timezone.utc))
        self.assertEqual(ctx.exception.code,'renewal_limit')
    def test_overdue_cannot_renew(self):
        loan=borrow_book(self.conn,10,1,datetime(2026,11,1,tzinfo=timezone.utc))
        with self.assertRaises(CirculationError) as ctx: update_loan(self.conn,loan['loan_id'],'renew',10,datetime(2026,12,1,tzinfo=timezone.utc))
        self.assertEqual(ctx.exception.code,'overdue')
    def test_five_active_loan_limit(self):
        for book_id in (1,2,4,5,6): borrow_book(self.conn,10,book_id)
        with self.assertRaises(CirculationError) as ctx: borrow_book(self.conn,10,7)
        self.assertEqual(ctx.exception.code,'loan_limit')
    def test_overdue_unreturned_loan_still_counts_toward_limit(self):
        for book_id in (1,2,4,5,6): borrow_book(self.conn,10,book_id)
        self.conn.execute("UPDATE loans SET due='2026-01-01' WHERE user_id=10")
        self.conn.commit()
        with self.assertRaises(CirculationError) as ctx: borrow_book(self.conn,10,7)
        self.assertEqual(ctx.exception.code,'loan_limit')
    def test_schema_migration_adds_fields_without_losing_legacy_loans(self):
        self.conn.execute("INSERT INTO loans(user_id,book_id,status,due,branch,created) VALUES(99,1,'Borrowed','2026-11-15','Central','2026-11-01')")
        self.conn.commit()
        self.conn.close()
        def factory():
            c=sqlite3.connect(self.path); c.row_factory=sqlite3.Row; return c
        setup(factory)
        self.conn=sqlite3.connect(self.path); self.conn.row_factory=sqlite3.Row
        cols={r['name'] for r in self.conn.execute('PRAGMA table_info(loans)')}
        self.assertIn('renew_count',cols); self.assertIn('returned_at',cols)
        self.assertEqual(self.conn.execute('SELECT status FROM loans WHERE user_id=99').fetchone()['status'],'Borrowed')
    def test_return_backfills_legacy_branch_inventory(self):
        self.conn.execute("INSERT INTO loans(user_id,book_id,status,due,branch,created) VALUES(21,3,'Borrowed','2026-11-15','Central','2026-11-01')")
        self.conn.commit()
        update_loan(self.conn,1,'return',21)
        row=self.conn.execute("SELECT total_copies,available_copies FROM library_inventory WHERE book_id=3 AND branch='Central'").fetchone()
        self.assertEqual((row['total_copies'],row['available_copies']),(1,1))
    def test_user_cannot_update_another_users_loan(self):
        loan=borrow_book(self.conn,10,1)
        with self.assertRaises(CirculationError) as ctx: update_loan(self.conn,loan['loan_id'],'return',11)
        self.assertEqual(ctx.exception.code,'not_found')

if __name__=='__main__': unittest.main()
