import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from market_restore_drill import restore_drill


class MarketRestoreDrillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backup = Path(self.tmp.name) / 'test.db'
        with sqlite3.connect(self.backup) as conn:
            conn.execute('CREATE TABLE users (id INTEGER)')
            conn.execute('CREATE TABLE books (id INTEGER)')
            conn.execute('INSERT INTO users VALUES (1)')
        self.sidecar = Path(str(self.backup) + '.sha256')
        self.write_digest()

    def write_digest(self):
        self.sidecar.write_text(f'{hashlib.sha256(self.backup.read_bytes()).hexdigest()}  {self.backup.name}\n')

    def test_restores_without_touching_original(self):
        original = self.backup.read_bytes()
        report = restore_drill(self.backup)
        self.assertEqual(report['result'], 'PASS')
        self.assertEqual(report['row_counts'], {'users': 1, 'books': 0})
        self.assertEqual(self.backup.read_bytes(), original)

    def test_rejects_modified_backup(self):
        with self.backup.open('ab') as f:
            f.write(b'tampered')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            restore_drill(self.backup)

    def test_rejects_missing_checksum(self):
        self.sidecar.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing checksum'):
            restore_drill(self.backup)

    def test_rejects_sidecar_pointing_to_another_file(self):
        self.sidecar.write_text('0' * 64 + '  another.db\n')
        with self.assertRaisesRegex(ValueError, 'Invalid checksum'):
            restore_drill(self.backup)

if __name__ == '__main__':
    unittest.main()
