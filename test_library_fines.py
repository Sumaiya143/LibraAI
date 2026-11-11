import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone

from circulation import setup as setup_circulation, borrow_book, update_loan, CirculationError
from library_fines import (
    outstanding_balance, user_fines, submit_payment, approve_payment,
    clearance_eligible, FineError, FINE_PER_DAY_PAISE,
)


class LibraryFineTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript("""
            CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT, email TEXT);
            INSERT INTO users VALUES(10,'Reader','reader@example.test'),(1,'Admin','admin@example.test');
            CREATE TABLE books(id INTEGER PRIMARY KEY,title TEXT,branch TEXT,stock INTEGER);
            INSERT INTO books VALUES(1,'Late Book','Central',2),(2,'New Book','Central',2);
            CREATE TABLE loans(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,status TEXT,due TEXT,branch TEXT,created TEXT);
        """)
        self.conn.close()
        def factory():
            c = sqlite3.connect(self.path)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys=ON")
            return c
        setup_circulation(factory)
        self.conn = factory()

    def tearDown(self):
        self.conn.close()
        os.unlink(self.path)

    def test_fourteen_day_loan_and_fine_starts_day_after_due(self):
        loan = borrow_book(self.conn, 10, 1, datetime(2026, 11, 1, tzinfo=timezone.utc))
        self.assertEqual(loan["due"], "2026-11-15")
        self.assertEqual(outstanding_balance(self.conn, 10, as_of=__import__("datetime").date(2026, 11, 15)), 0)
        update_loan(self.conn, loan["loan_id"], "return", 10, datetime(2026, 11, 18, tzinfo=timezone.utc))
        self.assertEqual(outstanding_balance(self.conn, 10, as_of=__import__("datetime").date(2026, 11, 18)), 3 * FINE_PER_DAY_PAISE)

    def test_unpaid_fine_blocks_new_borrow(self):
        loan = borrow_book(self.conn, 10, 1, datetime(2026, 10, 1, tzinfo=timezone.utc))
        update_loan(self.conn, loan["loan_id"], "return", 10, datetime(2026, 10, 20, tzinfo=timezone.utc))
        with self.assertRaises(CirculationError) as ctx:
            borrow_book(self.conn, 10, 2, datetime(2026, 10, 21, tzinfo=timezone.utc))
        self.assertEqual(ctx.exception.code, "fine_due")

    def test_payment_reference_requires_admin_approval_to_clear_balance(self):
        loan = borrow_book(self.conn, 10, 1, datetime(2026, 10, 1, tzinfo=timezone.utc))
        update_loan(self.conn, loan["loan_id"], "return", 10, datetime(2026, 10, 20, tzinfo=timezone.utc))
        result = submit_payment(self.conn, 10, "TXN-123", as_of=__import__("datetime").date(2026, 10, 20))
        self.assertGreater(result["amount_paise"], 0)
        self.assertFalse(clearance_eligible(self.conn, 10, as_of=__import__("datetime").date(2026, 10, 20)))
        approve_payment(self.conn, result["payment_id"], reviewer_id=1, now=datetime(2026, 10, 21, tzinfo=timezone.utc))
        self.assertEqual(outstanding_balance(self.conn, 10, as_of=__import__("datetime").date(2026, 10, 21)), 0)
        self.assertTrue(clearance_eligible(self.conn, 10, as_of=__import__("datetime").date(2026, 10, 21)))
        next_loan = borrow_book(self.conn, 10, 2, datetime(2026, 10, 22, tzinfo=timezone.utc))
        self.assertEqual(next_loan["due"], "2026-11-05")

    def test_active_overdue_loan_must_be_returned_before_payment_submission(self):
        borrow_book(self.conn, 10, 1, datetime(2026, 10, 1, tzinfo=timezone.utc))
        with self.assertRaises(FineError) as ctx:
            submit_payment(self.conn, 10, "TXN-456", as_of=__import__("datetime").date(2026, 10, 20))
        self.assertEqual(ctx.exception.code, "return_overdue_book_first")


    def test_legacy_returned_loan_without_timestamp_is_not_fined(self):
        self.conn.execute(
            "INSERT INTO loans(user_id,book_id,status,due,branch,created) VALUES(10,1,'Returned','2020-01-01','Central','2020-01-01')"
        )
        self.conn.commit()
        self.assertEqual(outstanding_balance(self.conn, 10, as_of=__import__("datetime").date(2026, 11, 11)), 0)

    def test_duplicate_payment_reference_rejected(self):
        loan = borrow_book(self.conn, 10, 1, datetime(2026, 10, 1, tzinfo=timezone.utc))
        update_loan(self.conn, loan["loan_id"], "return", 10, datetime(2026, 10, 20, tzinfo=timezone.utc))
        submit_payment(self.conn, 10, "TXN-DUP", as_of=__import__("datetime").date(2026, 10, 20))
        # First request remains pending; a second submission cannot create another.
        with self.assertRaises(FineError) as ctx:
            submit_payment(self.conn, 10, "TXN-DUP-2", as_of=__import__("datetime").date(2026, 10, 20))
        self.assertEqual(ctx.exception.code, "payment_pending")


if __name__ == "__main__":
    unittest.main()
