"""Offline operator-only import of licensed PDF/EPUB files into private storage.

No public upload endpoint. Run after confirming distribution rights.
"""
import argparse
import hashlib
import os
from pathlib import Path
import secrets
import sqlite3
import zipfile
import xml.etree.ElementTree as ET

from secure_ebook_delivery import setup

MAX_BYTES = 100 * 1024 * 1024

MAX_EPUB_ENTRIES = 2000
MAX_EPUB_UNCOMPRESSED = 250 * 1024 * 1024
MAX_EPUB_ENTRY_BYTES = 50 * 1024 * 1024


def validate_epub(path):
    """Bound ZIP metadata and require the EPUB container structure before import."""
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_EPUB_ENTRIES:
                raise ValueError('Invalid EPUB entry count')
            names = set()
            total = 0
            for entry in entries:
                name = entry.filename
                if (not name or name.startswith('/') or '\\' in name or
                    any(part in ('', '.', '..') for part in name.rstrip('/').split('/')) or
                    any(ord(c) < 32 for c in name)):
                    raise ValueError('Unsafe EPUB archive path')
                if name in names:
                    raise ValueError('Duplicate EPUB archive entry')
                names.add(name)
                if entry.flag_bits & 0x1:
                    raise ValueError('Encrypted EPUB entries are not supported')
                if entry.file_size > MAX_EPUB_ENTRY_BYTES:
                    raise ValueError('EPUB entry exceeds size limit')
                total += entry.file_size
                if total > MAX_EPUB_UNCOMPRESSED:
                    raise ValueError('EPUB exceeds uncompressed size limit')
            if 'mimetype' not in names or 'META-INF/container.xml' not in names:
                raise ValueError('Missing EPUB container metadata')
            mime_info = archive.getinfo('mimetype')
            if mime_info.compress_type != zipfile.ZIP_STORED or mime_info.file_size != 20:
                raise ValueError('Invalid EPUB mimetype entry')
            if archive.read('mimetype') != b'application/epub+zip':
                raise ValueError('Invalid EPUB mimetype')
            # Read only the bounded container metadata, not the entire archive.
            container = archive.getinfo('META-INF/container.xml')
            if container.file_size > 1024 * 1024:
                raise ValueError('EPUB container metadata too large')
            with archive.open(container) as stream:
                metadata = stream.read(1024 * 1024 + 1)
            if len(metadata) > 1024 * 1024 or b'<!DOCTYPE' in metadata.upper() or b'<!ENTITY' in metadata.upper():
                raise ValueError('Unsafe EPUB XML metadata')
            try:
                document = ET.fromstring(metadata)
            except ET.ParseError as exc:
                raise ValueError('Malformed EPUB container XML') from exc
            rootfiles = [node.attrib.get('full-path') for node in document.iter()
                         if node.tag.rsplit('}', 1)[-1] == 'rootfile']
            if not rootfiles or any(not path or path not in names or path.endswith('/')
                                    for path in rootfiles):
                raise ValueError('Missing EPUB package document')
            if any(not path.lower().endswith('.opf') for path in rootfiles):
                raise ValueError('Invalid EPUB package document extension')
    except (zipfile.BadZipFile, EOFError, RuntimeError) as exc:
        raise ValueError('Invalid EPUB archive') from exc



def ingest(conn, source, root, book_id, original_name=None):
    if type(book_id) is not int or book_id <= 0:
        raise ValueError('Invalid book ID')
    source = Path(source)
    if source.is_symlink() or not source.is_file():
        raise ValueError('Source must be a regular file')
    suffix = source.suffix.lower()
    if suffix not in ('.pdf', '.epub'):
        raise ValueError('Only PDF and EPUB supported')
    size = source.stat().st_size
    if not 0 < size <= MAX_BYTES:
        raise ValueError('File size outside allowed range')
    if suffix == '.pdf':
        with source.open('rb') as stream:
            if stream.read(5) != b'%PDF-':
                raise ValueError('Invalid PDF header')
    elif suffix == '.epub':
        validate_epub(source)
    name = original_name if original_name is not None else source.name
    if not isinstance(name, str) or not name or len(name) > 200 or '/' in name or '\\' in name or any(ord(c) < 32 for c in name):
        raise ValueError('Invalid display filename')
    if Path(name).suffix.lower() != suffix:
        raise ValueError('Display filename format mismatch')
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Private storage root is not a directory')
    setup(conn)
    if conn.execute('SELECT 1 FROM books WHERE id=?', (book_id,)).fetchone() is None:
        raise ValueError('Unknown book')
    if conn.execute('SELECT 1 FROM ebook_files WHERE book_id=?', (book_id,)).fetchone():
        raise ValueError('Existing mapping: explicit replacement process required')
    stored = secrets.token_hex(24) + suffix
    target = root / stored
    digest = hashlib.sha256()
    fd = None
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as output, source.open('rb') as input_file:
            fd = None
            total = 0
            for chunk in iter(lambda: input_file.read(1024 * 1024), b''):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError('File too large')
                output.write(chunk)
                digest.update(chunk)
            output.flush()
            os.fsync(output.fileno())
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute('SELECT 1 FROM ebook_files WHERE book_id=?', (book_id,)).fetchone():
            raise ValueError('Book mapping already exists')
        conn.execute('INSERT INTO ebook_files(book_id,stored_name,original_name,active,sha256_hex) VALUES(?,?,?,1,?)',
                     (book_id, stored, name, digest.hexdigest()))
        conn.commit()
        return {'book_id': book_id, 'stored_name': stored, 'sha256': digest.hexdigest(), 'bytes': total}
    except Exception:
        conn.rollback()
        if fd is not None:
            os.close(fd)
        target.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description='Import a licensed eBook into private storage')
    parser.add_argument('--db', required=True)
    parser.add_argument('--private-dir', required=True)
    parser.add_argument('--book-id', required=True, type=int)
    parser.add_argument('--file', required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        print(ingest(conn, args.file, args.private_dir, args.book_id))


if __name__ == '__main__':
    main()
