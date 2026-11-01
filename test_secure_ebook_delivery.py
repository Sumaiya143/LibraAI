import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from secure_ebook_delivery import private_file, safe_download_name, setup

class SecureEbookDeliveryTests(unittest.TestCase):
    def test_private_pdf_and_epub(self):
        with tempfile.TemporaryDirectory() as root:
            for name, mime in [('a.pdf', 'application/pdf'), ('a.epub', 'application/epub+zip')]:
                Path(root, name).write_bytes(b'test')
                path, got = private_file(root, name)
                self.assertEqual(path.read_bytes(), b'test')
                self.assertEqual(got, mime)
    def test_reject_traversal_and_other_extensions(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ('../secret.pdf', '/tmp/secret.pdf', 'a/../b.pdf', 'a.html', 'a\\b.pdf', '.hidden.pdf'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    private_file(root, name)
    def test_reject_symlink_escape(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as other:
            Path(other, 'secret.pdf').write_bytes(b'secret')
            try:
                Path(root, 'linked.pdf').symlink_to(Path(other, 'secret.pdf'))
            except (OSError, NotImplementedError):
                self.skipTest('Symlink unsupported')
            with self.assertRaises(ValueError):
                private_file(root, 'linked.pdf')
    def test_download_name_handles_windows_paths_and_control_characters(self):
        self.assertEqual(safe_download_name(r'C:\private\book.pdf', 7, '.pdf'), 'book.pdf')
        self.assertEqual(safe_download_name('../secret.pdf', 7, '.pdf'), 'secret.pdf')
        self.assertEqual(safe_download_name('bad\r\nname.pdf', 7, '.pdf'), 'badname.pdf')

    def test_download_name_falls_back_for_bad_metadata(self):
        for name in ('', None, 'book.exe', 'x' * 181 + '.pdf'):
            with self.subTest(name=name):
                self.assertEqual(safe_download_name(name, 9, '.pdf'), 'book-9.pdf')

    def test_mapping_schema(self):
        conn=sqlite3.connect(':memory:')
        conn.execute('CREATE TABLE books(id INTEGER PRIMARY KEY)')
        setup(conn)
        conn.execute("INSERT INTO books(id) VALUES(1)")
        conn.execute("INSERT INTO ebook_files(book_id,stored_name,original_name) VALUES(1,'abc.pdf','My Book.pdf')")
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO ebook_files(book_id,stored_name,original_name) VALUES(2,'abc.pdf','Another.pdf')")
        conn.close()

if __name__ == '__main__': unittest.main()
