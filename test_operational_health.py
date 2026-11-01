import sqlite3
import tempfile
import unittest
from pathlib import Path
from health_core import inspect_database


class OperationalHealthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_missing_database(self):
        self.assertFalse(inspect_database(str(self.tmp_path / 'missing.db'))['ok'])

    def test_empty_database_not_ready(self):
        p = self.tmp_path / 'empty.db'
        sqlite3.connect(p).close()
        self.assertFalse(inspect_database(str(p))['schema_ok'])

    def test_valid_schema_ready(self):
        p = self.tmp_path / 'ready.db'
        c = sqlite3.connect(p)
        try:
            for table in ('users', 'books', 'orders', 'loans', 'progress'):
                c.execute(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY)')
            c.commit()
        finally:
            c.close()
        self.assertEqual(inspect_database(str(p)), {'ok': True, 'schema_ok': True, 'integrity_ok': True})

    def test_corrupted_database_not_ready(self):
        p = self.tmp_path / 'bad.db'
        p.write_bytes(b'not sqlite')
        self.assertFalse(inspect_database(str(p))['ok'])


if __name__ == '__main__':
    unittest.main()

