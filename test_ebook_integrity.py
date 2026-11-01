import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from secure_ebook_delivery import setup, verify_file_digest

class EbookIntegrityTests(unittest.TestCase):
    def test_digest_valid_and_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'book.pdf'
            path.write_bytes(b'licensed original')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertTrue(verify_file_digest(path, digest))
            self.assertTrue(verify_file_digest(path, digest.upper()))
            path.write_bytes(b'tampered content')
            with self.assertRaises(ValueError):
                verify_file_digest(path, digest)
    def test_missing_and_malformed_digest_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'book.pdf'
            path.write_bytes(b'data')
            for digest in (None, '', '0'*63, 'z'*64, 123):
                with self.subTest(digest=digest), self.assertRaises(ValueError):
                    verify_file_digest(path, digest)
    def test_schema_migration_preserves_mapping(self):
        conn = sqlite3.connect(':memory:')
        conn.execute('CREATE TABLE books(id INTEGER PRIMARY KEY)')
        conn.execute('INSERT INTO books VALUES (1)')
        conn.execute('CREATE TABLE ebook_files(book_id INTEGER PRIMARY KEY, stored_name TEXT NOT NULL UNIQUE, original_name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1)')
        conn.execute("INSERT INTO ebook_files VALUES(1,'stored.pdf','Book.pdf',1)")
        setup(conn)
        self.assertIn('sha256_hex', [r[1] for r in conn.execute('PRAGMA table_info(ebook_files)')])
        self.assertEqual(conn.execute('SELECT stored_name FROM ebook_files WHERE book_id=1').fetchone()[0], 'stored.pdf')
        setup(conn)
        conn.close()

if __name__ == '__main__': unittest.main()
