import hashlib
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from zipfile import ZipFile
import hashlib
from release_archive import build_archive

class ArchiveSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'source'
        self.root.mkdir()
        for name in ('app.py','requirements.txt','Dockerfile','.env.example','buyer_preflight.py','compose.market.yaml','Caddyfile','payment_routes.py','digital_entitlements.py'):
            (self.root/name).write_text('safe')
        self.output = Path(self.temp.name)/'release.zip'

    def test_clean_archive(self):
        build_archive(self.root,self.output)
        with ZipFile(self.output) as z:
            self.assertIsNone(z.testzip())
            self.assertIn('LibraAI/app.py',z.namelist())


    def test_archive_is_reproducible_when_source_mtimes_change(self):
        build_archive(self.root, self.output)
        first = hashlib.sha256(self.output.read_bytes()).hexdigest()
        # Changing filesystem timestamps must not affect release ZIP metadata.
        source = self.root / 'app.py'
        os.utime(source, (1_700_000_000, 1_700_000_000))
        second_output = Path(self.temp.name) / 'release-second.zip'
        build_archive(self.root, second_output)
        second = hashlib.sha256(second_output.read_bytes()).hexdigest()
        self.assertEqual(first, second)

    def test_archive_entries_have_normalized_timestamps_and_permissions(self):
        build_archive(self.root, self.output)
        with ZipFile(self.output) as archive:
            info = archive.getinfo('LibraAI/app.py')
            self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
            self.assertEqual((info.external_attr >> 16) & 0o777, 0o644)

    def test_missing_payment_deployment_file_rejected(self):
        (self.root / 'payment_routes.py').unlink()
        with self.assertRaisesRegex(ValueError, 'payment_routes.py'):
            build_archive(self.root, self.output)

    def test_release_manifest_matches_archived_file_contents(self):
        build_archive(self.root, self.output)
        with ZipFile(self.output) as archive:
            manifest = archive.read('LibraAI/RELEASE_MANIFEST.sha256').decode('utf-8')
            entries = [line.split('  ', 1) for line in manifest.splitlines()]
            self.assertEqual(len(entries), len(archive.namelist()) - 1)
            for expected, member in entries:
                self.assertEqual(hashlib.sha256(archive.read(member)).hexdigest(), expected)

    def test_manifest_is_deterministic(self):
        build_archive(self.root, self.output)
        first = hashlib.sha256(self.output.read_bytes()).hexdigest()
        os.utime(self.root / 'app.py', (1_600_000_000, 1_600_000_000))
        second_output = Path(self.temp.name) / 'release-manifest-second.zip'
        build_archive(self.root, second_output)
        self.assertEqual(first, hashlib.sha256(second_output.read_bytes()).hexdigest())

    def test_secret_rejected(self):
        (self.root/'.env').write_text('SECRET=bad')
        with self.assertRaises(ValueError): build_archive(self.root,self.output)

    def test_database_rejected(self):
        (self.root/'customers.sqlite3').write_text('private')
        with self.assertRaises(ValueError): build_archive(self.root,self.output)

    def test_symlink_rejected(self):
        try:
            (self.root/'link').symlink_to(self.root/'app.py')
        except OSError:
            self.skipTest('Symlinks not supported on this platform without elevated privileges')
        with self.assertRaises(ValueError): build_archive(self.root,self.output)

    def test_development_cache_excluded(self):
        cache = self.root/'__pycache__'; cache.mkdir()
        (cache/'file.pyc').write_bytes(b'bad')
        build_archive(self.root,self.output)
        with ZipFile(self.output) as z:
            self.assertFalse(any('__pycache__' in n for n in z.namelist()))

if __name__=='__main__': unittest.main()

class AtomicReleaseArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / 'source'
        self.root.mkdir()
        for name in ('app.py', 'requirements.txt', 'Dockerfile', '.env.example', 'buyer_preflight.py', 'compose.market.yaml', 'Caddyfile', 'payment_routes.py', 'digital_entitlements.py'):
            (self.root / name).write_text('safe')
        self.output = base / 'release.zip'

    def test_existing_release_survives_preflight_failure(self):
        self.output.write_bytes(b'previous-valid-release-placeholder')
        before = self.output.read_bytes()
        (self.root / '.env').write_text('SECRET=must-not-package')
        with self.assertRaises(ValueError):
            build_archive(self.root, self.output)
        self.assertEqual(self.output.read_bytes(), before)

    def test_existing_release_survives_archive_write_failure(self):
        from unittest.mock import patch
        self.output.write_bytes(b'previous-release')
        before = self.output.read_bytes()
        import release_archive
        with patch.object(release_archive, '_copy_and_hash', side_effect=OSError('simulated disk failure')):
            with self.assertRaises(OSError):
                build_archive(self.root, self.output)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertFalse(list(self.output.parent.glob(f'.{self.output.name}.*.tmp')))
