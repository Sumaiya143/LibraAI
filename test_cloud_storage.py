import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cloud_storage
from cloud_storage import CloudStorageProvider, normalize_key


class StorageKeyTests(unittest.TestCase):
    def test_rejects_traversal_absolute_and_ambiguous_keys(self):
        for key in ('', '/absolute.pdf', '../secret', 'a/../../secret', 'a//b',
                    './book.pdf', 'a/./book.pdf', 'a/../book.pdf', 'folder/',
                    'C:\\outside\\book.pdf', 'bad\x00key'):
            with self.subTest(key=key), self.assertRaises((TypeError, ValueError)):
                normalize_key(key)
        with self.assertRaises(TypeError):
            normalize_key(None)

    def test_normalizes_safe_nested_key(self):
        self.assertEqual(normalize_key('covers\\fiction/book one.pdf'), 'covers/fiction/book one.pdf')


class LocalStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.provider = CloudStorageProvider(backend='local', local_root=self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_round_trip_exists_and_encoded_download_url(self):
        result = self.provider.put_object('covers/my book.pdf', b'content', 'application/pdf')
        self.assertEqual(result['backend'], 'local')
        self.assertEqual(result['size'], 7)
        self.assertEqual(len(result['sha256']), 64)
        self.assertTrue(self.provider.exists('covers/my book.pdf'))
        self.assertEqual(self.provider.get_object('covers/my book.pdf'), b'content')
        self.assertEqual(self.provider.generate_download_url('covers/my book.pdf'),
                         '/api/storage/download?key=covers%2Fmy+book.pdf')
        self.assertIsNone(self.provider.get_object('covers/missing.pdf'))

    def test_bounded_byte_range_streaming(self):
        self.provider.put_object('audio/chapter.mp3', b'0123456789', 'audio/mpeg')
        self.assertEqual(self.provider.object_size('audio/chapter.mp3'), 10)
        self.assertEqual(b''.join(self.provider.iter_object_range('audio/chapter.mp3', 3, 6)), b'3456')
        self.assertEqual(b''.join(self.provider.iter_object_range('audio/chapter.mp3', 0, 9, chunk_size=3)), b'0123456789')
        self.assertIsNone(self.provider.object_size('audio/missing.mp3'))

    def test_expiry_is_bounded(self):
        for value in (0, -1, 604801, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.provider.generate_download_url('book.pdf', value)


class CloudStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.provider = CloudStorageProvider(backend='s3', local_root=self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_cloud_credentials_fail_without_local_fallback(self):
        with patch.multiple(cloud_storage, S3_ACCESS_KEY='', S3_SECRET_KEY=''):
            with self.assertRaisesRegex(RuntimeError, 'requires a bucket'):
                self.provider.put_object('private.pdf', b'private')
        self.assertFalse((Path(self.temp.name) / 'private.pdf').exists())

    def test_cloud_read_error_never_returns_stale_local_object(self):
        (Path(self.temp.name) / 'book.pdf').write_bytes(b'local-copy')

        class OfflineClient:
            def get_object(self, **kwargs):
                raise RuntimeError('provider unavailable')

        self.provider._s3_client = OfflineClient()
        with patch.multiple(cloud_storage, S3_BUCKET='bucket', S3_ACCESS_KEY='key', S3_SECRET_KEY='secret'):
            with self.assertRaisesRegex(RuntimeError, 'provider unavailable'):
                self.provider.get_object('book.pdf')

    def test_invalid_backend_is_rejected(self):
        with self.assertRaises(ValueError):
            CloudStorageProvider(backend='unknown', local_root=self.temp.name)


if __name__ == '__main__':
    unittest.main()
