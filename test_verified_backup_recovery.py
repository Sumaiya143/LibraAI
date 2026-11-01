import sqlite3
import tempfile
import unittest
from pathlib import Path
from backup_manager import backup_database
from backup_manifest import create_manifest
from backup_restore_drill import run_verified_backup_drill


class VerifiedBackupRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.db'
        self.backup = self.root / 'backup.db'
        self.manifest = self.root / 'backup.manifest.json'
        self.key = b'K' * 40
        with sqlite3.connect(self.source) as conn:
            conn.execute('CREATE TABLE users(id INTEGER, name TEXT)')
            conn.execute('CREATE TABLE books(id INTEGER, title TEXT)')
            conn.execute("INSERT INTO users VALUES (1, 'Private Name')")
        backup_database(self.source, self.backup)

    def test_authenticated_recovery(self):
        create_manifest(self.backup, self.manifest, self.key)
        result = run_verified_backup_drill(self.backup, self.manifest, self.key)
        self.assertTrue(result['verified_backup_restore'])
        self.assertTrue(result['manifest_authenticated'])
        self.assertNotIn('Private Name', str(result))

    def test_unsigned_rejected_by_default(self):
        create_manifest(self.backup, self.manifest)
        with self.assertRaises(ValueError):
            run_verified_backup_drill(self.backup, self.manifest)

    def test_unsigned_legacy_opt_in(self):
        create_manifest(self.backup, self.manifest)
        result = run_verified_backup_drill(self.backup, self.manifest, require_hmac=False)
        self.assertFalse(result['manifest_authenticated'])

    def test_wrong_secret_rejected(self):
        create_manifest(self.backup, self.manifest, self.key)
        with self.assertRaises(ValueError):
            run_verified_backup_drill(self.backup, self.manifest, b'X' * 40)

    def test_tampered_backup_rejected(self):
        create_manifest(self.backup, self.manifest, self.key)
        with open(self.backup, 'ab') as output:
            output.write(b'altered')
        with self.assertRaises(ValueError):
            run_verified_backup_drill(self.backup, self.manifest, self.key)

    def test_original_backup_not_changed(self):
        create_manifest(self.backup, self.manifest, self.key)
        before = self.backup.read_bytes()
        run_verified_backup_drill(self.backup, self.manifest, self.key)
        self.assertEqual(before, self.backup.read_bytes())
