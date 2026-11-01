import json
import os
import tempfile
import unittest
from pathlib import Path
from payment_report_manifest import create_manifest, verify_manifest


class PaymentReportManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.csv = self.root / 'issues.csv'
        self.csv.write_bytes(b'\xef\xbb\xbfattempt_id,order_id,issue\r\n1,2,missing_order\r\n')
        self.manifest = self.root / 'issues.manifest.json'

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_and_verify(self):
        result = create_manifest(self.csv, self.manifest)
        self.assertEqual(result['size_bytes'], self.csv.stat().st_size)
        self.assertTrue(verify_manifest(self.csv, self.manifest)['valid'])

    def test_modified_csv_fails_verification(self):
        create_manifest(self.csv, self.manifest)
        self.csv.write_bytes(self.csv.read_bytes() + b'3,4,missing_order\r\n')
        self.assertFalse(verify_manifest(self.csv, self.manifest)['valid'])

    def test_manifest_does_not_overwrite(self):
        self.manifest.write_text('original')
        with self.assertRaises(FileExistsError):
            create_manifest(self.csv, self.manifest)
        self.assertEqual(self.manifest.read_text(), 'original')

    def test_rejects_wrong_header(self):
        self.csv.write_text('customer_email,secret\n')
        with self.assertRaises(ValueError):
            create_manifest(self.csv, self.manifest)

    def test_rejects_invalid_manifest_checksum(self):
        self.manifest.write_text(json.dumps({'schema': 'libraai-payment-reconciliation-manifest-v1',
            'file_name': self.csv.name, 'sha256': 'bad', 'size_bytes': self.csv.stat().st_size}))
        with self.assertRaises(ValueError):
            verify_manifest(self.csv, self.manifest)


    def test_hmac_signed_manifest_authenticates(self):
        os.environ['LIBRAAI_TEST_REPORT_KEY'] = 'a-secure-test-key-with-at-least-32-bytes'
        try:
            create_manifest(self.csv, self.manifest, 'LIBRAAI_TEST_REPORT_KEY')
            result = verify_manifest(self.csv, self.manifest, 'LIBRAAI_TEST_REPORT_KEY')
            self.assertTrue(result['valid'])
            self.assertTrue(result['authenticated'])
        finally:
            os.environ.pop('LIBRAAI_TEST_REPORT_KEY', None)

    def test_signed_manifest_requires_key(self):
        os.environ['LIBRAAI_TEST_REPORT_KEY'] = 'a-secure-test-key-with-at-least-32-bytes'
        try:
            create_manifest(self.csv, self.manifest, 'LIBRAAI_TEST_REPORT_KEY')
            with self.assertRaisesRegex(ValueError, 'requires --hmac-key-env'):
                verify_manifest(self.csv, self.manifest)
        finally:
            os.environ.pop('LIBRAAI_TEST_REPORT_KEY', None)

    def test_wrong_hmac_key_fails(self):
        os.environ['LIBRAAI_TEST_REPORT_KEY'] = 'a-secure-test-key-with-at-least-32-bytes'
        os.environ['LIBRAAI_TEST_WRONG_KEY'] = 'a-different-test-key-with-at-least-32b'
        try:
            create_manifest(self.csv, self.manifest, 'LIBRAAI_TEST_REPORT_KEY')
            with self.assertRaisesRegex(ValueError, 'HMAC authentication failed'):
                verify_manifest(self.csv, self.manifest, 'LIBRAAI_TEST_WRONG_KEY')
        finally:
            os.environ.pop('LIBRAAI_TEST_REPORT_KEY', None)
            os.environ.pop('LIBRAAI_TEST_WRONG_KEY', None)

    def test_signed_manifest_metadata_tampering_fails(self):
        os.environ['LIBRAAI_TEST_REPORT_KEY'] = 'a-secure-test-key-with-at-least-32-bytes'
        try:
            create_manifest(self.csv, self.manifest, 'LIBRAAI_TEST_REPORT_KEY')
            data = json.loads(self.manifest.read_text())
            data['file_name'] = 'other.csv'
            self.manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'HMAC authentication failed'):
                verify_manifest(self.csv, self.manifest, 'LIBRAAI_TEST_REPORT_KEY')
        finally:
            os.environ.pop('LIBRAAI_TEST_REPORT_KEY', None)

    def test_hmac_key_must_be_at_least_32_bytes(self):
        os.environ['LIBRAAI_TEST_REPORT_KEY'] = 'short'
        try:
            with self.assertRaisesRegex(ValueError, 'at least 32'):
                create_manifest(self.csv, self.manifest, 'LIBRAAI_TEST_REPORT_KEY')
        finally:
            os.environ.pop('LIBRAAI_TEST_REPORT_KEY', None)

    def test_key_cannot_be_supplied_for_unsigned_manifest(self):
        create_manifest(self.csv, self.manifest)
        os.environ['LIBRAAI_TEST_REPORT_KEY'] = 'a-secure-test-key-with-at-least-32-bytes'
        try:
            with self.assertRaisesRegex(ValueError, 'manifest is unsigned'):
                verify_manifest(self.csv, self.manifest, 'LIBRAAI_TEST_REPORT_KEY')
        finally:
            os.environ.pop('LIBRAAI_TEST_REPORT_KEY', None)

    def test_duplicate_json_keys_are_rejected(self):
        create_manifest(self.csv, self.manifest)
        raw = self.manifest.read_text(encoding='utf-8')
        self.manifest.write_text(raw.replace('"schema": "libraai-payment-reconciliation-manifest-v1",',
            '"schema": "libraai-payment-reconciliation-manifest-v1",\n  "schema": "libraai-payment-reconciliation-manifest-v1",'), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Invalid manifest JSON'):
            verify_manifest(self.csv, self.manifest)

    def test_manifest_has_no_customer_or_gateway_fields(self):
        data = create_manifest(self.csv, self.manifest)
        self.assertNotIn('customer_email', data)
        self.assertNotIn('provider_ref', data)


if __name__ == '__main__':
    unittest.main()
