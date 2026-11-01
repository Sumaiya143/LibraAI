import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from backup_manifest import create_manifest, verify_manifest


class BackupManifestTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / 'backup.db'
        self.manifest = Path(temp.name) / 'backup.json'
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE TABLE users (id INTEGER)')
            conn.execute('CREATE TABLE books (id INTEGER)')
        self.key = b'x' * 32

    def test_unsigned_roundtrip(self):
        create_manifest(self.db, self.manifest)
        self.assertFalse(verify_manifest(self.db, self.manifest)['authenticated'])

    def test_signed_roundtrip(self):
        create_manifest(self.db, self.manifest, self.key)
        self.assertTrue(verify_manifest(self.db, self.manifest, self.key, True)['authenticated'])

    def test_wrong_key_rejected(self):
        create_manifest(self.db, self.manifest, self.key)
        with self.assertRaises(ValueError):
            verify_manifest(self.db, self.manifest, b'y' * 32)

    def test_unsigned_rejected_when_signature_required(self):
        create_manifest(self.db, self.manifest)
        with self.assertRaises(ValueError):
            verify_manifest(self.db, self.manifest, self.key, True)

    def test_modified_database_rejected(self):
        create_manifest(self.db, self.manifest)
        with sqlite3.connect(self.db) as conn:
            conn.execute('INSERT INTO books VALUES (1)')
        with self.assertRaises(ValueError):
            verify_manifest(self.db, self.manifest)

    def test_manifest_tampering_rejected(self):
        create_manifest(self.db, self.manifest, self.key)
        data = json.loads(self.manifest.read_text())
        data['filename'] = 'other.db'
        self.manifest.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            verify_manifest(self.db, self.manifest, self.key)

    def test_existing_manifest_not_overwritten(self):
        create_manifest(self.db, self.manifest)
        with self.assertRaises(FileExistsError):
            create_manifest(self.db, self.manifest)

    def test_short_key_rejected(self):
        with self.assertRaises(ValueError):
            create_manifest(self.db, self.manifest, b'weak')
