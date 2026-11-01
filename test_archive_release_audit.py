import tempfile
import unittest
import zipfile
from pathlib import Path
from archive_release_audit import audit_archive


class ArchiveReleaseAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'handoff.zip'

    def create(self, entries):
        with zipfile.ZipFile(self.path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, value in entries:
                archive.writestr(name, value)
        return audit_archive(self.path)

    def test_safe_archive(self):
        self.assertTrue(self.create([('LibraAI/app.py', 'print(1)')])['safe_for_handoff_review'])

    def test_traversal(self):
        self.assertIn('unsafe_entry_path', self.create([('../secret', 'x')])['issues'])

    def test_windows_separator(self):
        # Python 3.15 zipfile normalizes backslashes in writestr(), so inject raw backslash in ZIP bytes.
        with zipfile.ZipFile(self.path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('folder/secret', 'x')
        with open(self.path, 'rb') as f:
            data = f.read()
        data = data.replace(b'folder/secret', b'folder' + b'\\' + b'secret')
        with open(self.path, 'wb') as f:
            f.write(data)
        self.assertIn('unsafe_entry_path', audit_archive(self.path)['issues'])

    def test_windows_reserved_device_name(self):
        self.assertIn('nonportable_entry_path', self.create([('LibraAI/CON.txt', 'x')])['issues'])

    def test_windows_alternate_data_stream(self):
        self.assertIn('nonportable_entry_path', self.create([('LibraAI/app.py:payload', 'x')])['issues'])

    def test_trailing_dot_or_space_path(self):
        self.assertIn('nonportable_entry_path', self.create([('LibraAI/report. ', 'x')])['issues'])

    def test_unicode_normalization_path_collision(self):
        composed = 'LibraAI/caf\u00e9.txt'
        decomposed = 'LibraAI/cafe\u0301.txt'
        result = self.create([(composed, 'a'), (decomposed, 'b')])
        self.assertIn('duplicate_entry_path', result['issues'])

    def test_duplicate_casefold(self):
        self.assertIn('duplicate_entry_path', self.create([('app.py', 'a'), ('APP.py', 'b')])['issues'])

    def test_nested_secret(self):
        self.assertIn('prohibited_entry', self.create([('LibraAI/config/.env.production', 'secret')])['issues'])

    def test_database(self):
        self.assertIn('prohibited_entry', self.create([('LibraAI/customer.db', 'data')])['issues'])

    def test_corrupt_archive(self):
        self.path.write_bytes(b'not a zip')
        self.assertIn('invalid_or_corrupt_archive', audit_archive(self.path)['issues'])

    def test_detects_private_key_in_source_content(self):
        marker = '-----BEGIN RSA ' + 'PRIVATE KEY-----'
        result = self.create([('LibraAI/config.py', 'KEY = ' + repr(marker))])
        self.assertIn('possible_secret_content', result['issues'])

    def test_detects_provider_token_signature_in_text(self):
        token = 'AKIA' + 'ABCDEFGHIJKLMNOP'
        result = self.create([('LibraAI/config.txt', 'cloud key: ' + token)])
        self.assertIn('possible_secret_content', result['issues'])

    def test_does_not_flag_safe_placeholder_text(self):
        result = self.create([('LibraAI/.env.example', 'API_KEY=replace-with-your-key\n')])
        self.assertTrue(result['safe_for_handoff_review'])

    def test_allows_production_environment_template_but_not_real_env(self):
        result = self.create([('LibraAI/.env.production.example', 'SECRET_KEY=replace-with-a-long-random-secret\n')])
        self.assertTrue(result['safe_for_handoff_review'], result)


    def test_scans_bounded_prefix_of_large_text_file(self):
        # Files above the scan limit should still have their first 2 MiB inspected.
        token = 'AKIA' + 'ABCDEFGHIJKLMNOP'
        payload = ('cloud key: ' + token + '\n').encode() + (b'x' * (2 * 1024 * 1024 + 128))
        with zipfile.ZipFile(self.path, 'w', compression=zipfile.ZIP_STORED) as archive:
            archive.writestr('LibraAI/config.txt', payload)
        result = audit_archive(self.path)
        self.assertIn('possible_secret_content', result['issues'])

    def test_large_text_file_scan_detects_secret_after_old_limit(self):
        # Scan continues beyond the former 2 MiB prefix without buffering the whole file.
        token = 'AKIA' + 'ABCDEFGHIJKLMNOP'
        payload = (b'x' * (2 * 1024 * 1024 + 128)) + ('cloud key: ' + token).encode()
        with zipfile.ZipFile(self.path, 'w', compression=zipfile.ZIP_STORED) as archive:
            archive.writestr('LibraAI/config.txt', payload)
        result = audit_archive(self.path)
        self.assertIn('possible_secret_content', result['issues'])

    def test_nul_prefix_does_not_disable_secret_scan(self):
        # A NUL byte must not make an eligible source file exempt from scanning.
        token = 'AKIA' + 'ABCDEFGHIJKLMNOP'
        payload = b'\x00' + b'x' * 128 + ('cloud key: ' + token).encode()
        result = self.create([('LibraAI/config.py', payload)])
        self.assertIn('possible_secret_content', result['issues'])

    def test_secret_signature_split_across_read_chunk_is_detected(self):
        token = 'AKIA' + 'ABCDEFGHIJKLMNOP'
        # Place a token across the 64 KiB stream-read boundary.
        prefix = b'x' * (64 * 1024 - 3) + b' '
        payload = prefix + token.encode() + b' ' + (b'x' * 128)
        with zipfile.ZipFile(self.path, 'w', compression=zipfile.ZIP_STORED) as archive:
            archive.writestr('LibraAI/config.txt', payload)
        result = audit_archive(self.path)
        self.assertIn('possible_secret_content', result['issues'])

    def test_symlink(self):
        import stat
        with zipfile.ZipFile(self.path, 'w') as archive:
            info = zipfile.ZipInfo('LibraAI/linked')
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, '../outside')
        self.assertIn('symlink_entry', audit_archive(self.path)['issues'])
