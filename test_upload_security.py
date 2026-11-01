import os
import unittest
from unittest.mock import patch

from upload_security import EICAR, inspect_upload


class UploadSecurityTests(unittest.TestCase):
    def test_rejects_known_antivirus_test_signature(self):
        accepted, status, _ = inspect_upload('sample.pdf', b'%PDF-1.7\n' + EICAR)
        self.assertFalse(accepted)
        self.assertEqual(status, 'infected')

    def test_rejects_extension_content_mismatch(self):
        accepted, status, _ = inspect_upload('image.png', b'<html>not a png</html>')
        self.assertFalse(accepted)
        self.assertEqual(status, 'invalid')

    def test_reports_not_scanned_when_clamav_is_not_configured(self):
        with patch.dict(os.environ, {'LIBRAAI_CLAMAV_HOST': ''}, clear=False):
            accepted, status, _ = inspect_upload('sample.pdf', b'%PDF-1.7\nvalid-looking content')
        self.assertTrue(accepted)
        self.assertEqual(status, 'not_scanned')

    def test_fails_closed_when_scanning_is_required_but_unavailable(self):
        with patch.dict(os.environ, {'LIBRAAI_CLAMAV_HOST': '', 'LIBRAAI_REQUIRE_MALWARE_SCAN': '1'}, clear=False):
            accepted, status, message = inspect_upload('sample.pdf', b'%PDF-1.7\nvalid-looking content')
        self.assertFalse(accepted)
        self.assertEqual(status, 'unavailable')
        self.assertIn('required', message)

    def test_accepts_valid_signature_when_scanner_is_unconfigured(self):
        with patch.dict(os.environ, {'LIBRAAI_CLAMAV_HOST': '', 'LIBRAAI_REQUIRE_MALWARE_SCAN': '0'}, clear=False):
            accepted, status, _ = inspect_upload('cover.webp', b'RIFF' + b'\x00\x00\x00\x00' + b'WEBP' + b'data')
        self.assertTrue(accepted)
        self.assertEqual(status, 'not_scanned')


if __name__ == '__main__':
    unittest.main()
