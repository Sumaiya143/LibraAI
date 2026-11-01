import tempfile
import unittest
import zipfile
from pathlib import Path
from ebook_ingest import validate_epub

class EpubContainerSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'book.epub'

    def build(self, container, include_opf=True):
        with zipfile.ZipFile(self.path, 'w') as z:
            z.writestr('mimetype', b'application/epub+zip', compress_type=zipfile.ZIP_STORED)
            z.writestr('META-INF/container.xml', container)
            if include_opf:
                z.writestr('OPS/book.opf', b'<package/>')

    def test_namespaced_valid_container(self):
        self.build(b'<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>')
        validate_epub(self.path)

    def test_missing_package_file_rejected(self):
        self.build(b'<container><rootfile full-path="OPS/missing.opf"/></container>')
        with self.assertRaises(ValueError): validate_epub(self.path)

    def test_malformed_container_rejected(self):
        self.build(b'<container><rootfile full-path="OPS/book.opf"/>')
        with self.assertRaises(ValueError): validate_epub(self.path)

    def test_xml_entity_declaration_rejected(self):
        self.build(b'<!DOCTYPE container [<!ENTITY test "x">]><container><rootfile full-path="OPS/book.opf"/></container>')
        with self.assertRaises(ValueError): validate_epub(self.path)

    def test_wrong_package_extension_rejected(self):
        self.build(b'<container><rootfile full-path="OPS/book.txt"/></container>', False)
        with zipfile.ZipFile(self.path, 'a') as z: z.writestr('OPS/book.txt', 'text')
        with self.assertRaises(ValueError): validate_epub(self.path)
