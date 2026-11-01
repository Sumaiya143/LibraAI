import sqlite3
import tempfile
import unittest
from pathlib import Path
from ebook_ingest import ingest
from secure_ebook_delivery import private_file, verify_file_digest


class EbookIngestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.storage = self.root / 'private'
        self.storage.mkdir()
        self.conn = sqlite3.connect(':memory:')
        self.addCleanup(self.conn.close)
        self.conn.execute('CREATE TABLE books(id INTEGER PRIMARY KEY)')
        self.conn.execute('INSERT INTO books VALUES(7)')
        self.source = self.root / 'licensed.pdf'
        self.source.write_bytes(b'%PDF-1.4\nexample')

    def test_import_integrity_and_private_lookup(self):
        result = ingest(self.conn, self.source, self.storage, 7)
        path, mime = private_file(self.storage, result['stored_name'])
        self.assertEqual(mime, 'application/pdf')
        self.assertTrue(verify_file_digest(path, result['sha256']))
        self.assertEqual(self.conn.execute('SELECT sha256_hex FROM ebook_files').fetchone()[0], result['sha256'])

    def test_duplicate_rejected_without_extra_files(self):
        ingest(self.conn, self.source, self.storage, 7)
        with self.assertRaises(ValueError):
            ingest(self.conn, self.source, self.storage, 7)
        self.assertEqual(len(list(self.storage.iterdir())), 1)

    def test_invalid_header_rejected(self):
        self.source.write_bytes(b'not a pdf')
        with self.assertRaises(ValueError):
            ingest(self.conn, self.source, self.storage, 7)
        self.assertEqual(list(self.storage.iterdir()), [])

    def test_unknown_book_rejected(self):
        with self.assertRaises(ValueError):
            ingest(self.conn, self.source, self.storage, 99)

    def test_path_like_display_name_rejected(self):
        with self.assertRaises(ValueError):
            ingest(self.conn, self.source, self.storage, 7, '../bad.pdf')

    def test_symlink_source_rejected(self):
        link = self.root / 'link.pdf'
        try:
            link.symlink_to(self.source)
        except (OSError, NotImplementedError):
            self.skipTest('Symlinks unsupported')
        with self.assertRaises(ValueError):
            ingest(self.conn, link, self.storage, 7)

if __name__ == '__main__':
    unittest.main()

class EpubValidationTests(unittest.TestCase):
    def setUp(self):
        import zipfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'book.epub'
        self.zipfile = zipfile

    def build(self, extra=(), mime=b'application/epub+zip'):
        with self.zipfile.ZipFile(self.path, 'w') as archive:
            archive.writestr('mimetype', mime, compress_type=self.zipfile.ZIP_STORED)
            archive.writestr('META-INF/container.xml', b'<container><rootfile full-path="OEBPS/content.opf"/></container>')
            for name, content in extra:
                archive.writestr(name, content)

    def test_valid_epub(self):
        from ebook_ingest import validate_epub
        self.build([('OEBPS/content.opf', '<package/>')])
        validate_epub(self.path)

    def test_reject_traversal(self):
        from ebook_ingest import validate_epub
        self.build([('../outside.txt', 'bad')])
        with self.assertRaises(ValueError):
            validate_epub(self.path)

    def test_reject_missing_container(self):
        from ebook_ingest import validate_epub
        with self.zipfile.ZipFile(self.path, 'w') as archive:
            archive.writestr('mimetype', b'application/epub+zip', compress_type=self.zipfile.ZIP_STORED)
        with self.assertRaises(ValueError):
            validate_epub(self.path)

    def test_reject_oversized_uncompressed_entry(self):
        from ebook_ingest import validate_epub, MAX_EPUB_ENTRY_BYTES
        self.build([('OEBPS/huge.xhtml', b'A' * (MAX_EPUB_ENTRY_BYTES + 1))])
        with self.assertRaises(ValueError):
            validate_epub(self.path)

    def test_reject_wrong_mimetype(self):
        from ebook_ingest import validate_epub
        self.build(mime=b'application/zip')
        with self.assertRaises(ValueError):
            validate_epub(self.path)
