"""Regression tests for SQLite context-manager lifecycle in the shared DB helper."""
import os
import sqlite3
import tempfile
import unittest

import server


class DatabaseConnectionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.original_db = server.DB
        self.tempdir = tempfile.TemporaryDirectory()
        server.DB = os.path.join(self.tempdir.name, "lifecycle.sqlite3")
        server.init()

    def tearDown(self):
        server.DB = self.original_db
        self.tempdir.cleanup()

    def test_context_exit_closes_connection(self):
        with server.db() as connection:
            self.assertEqual(connection.execute("SELECT 1").fetchone()[0], 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_exception_rolls_back_and_closes_connection(self):
        with server.db() as connection:
            connection.execute("CREATE TABLE lifecycle_test (value TEXT)")
        with self.assertRaisesRegex(RuntimeError, "force rollback"):
            with server.db() as connection:
                connection.execute("INSERT INTO lifecycle_test(value) VALUES('not saved')")
                raise RuntimeError("force rollback")
        with server.db() as connection:
            count = connection.execute("SELECT COUNT(*) FROM lifecycle_test").fetchone()[0]
        self.assertEqual(count, 0)
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")


if __name__ == "__main__":
    unittest.main()
