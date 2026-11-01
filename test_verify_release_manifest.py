import hashlib
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from verify_release_manifest import MANIFEST_NAME, verify_release_manifest


def make_archive(path, files, manifest_override=None):
    entries = dict(files)
    lines = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n'
                    for name, data in sorted(entries.items()))
    entries[MANIFEST_NAME] = (manifest_override if isinstance(manifest_override, bytes)
                              else (manifest_override if manifest_override is not None else lines).encode('utf-8'))
    with ZipFile(path, 'w', ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


class VerifyReleaseManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.archive = Path(self.temp.name) / 'release.zip'
        self.files = {'LibraAI/app.py': b'print("hello")',
                      'LibraAI/README.md': b'Buyer handover'}

    def test_valid_manifest_verifies(self):
        make_archive(self.archive, self.files)
        result = verify_release_manifest(self.archive)
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['checked_files'], 2)

    def test_modified_file_fails_hash_check(self):
        make_archive(self.archive, self.files)
        with ZipFile(self.archive, 'a', ZIP_DEFLATED) as archive:
            # Duplicate members are rejected rather than ambiguously selected.
            archive.writestr('LibraAI/app.py', b'changed')
        result = verify_release_manifest(self.archive)
        self.assertFalse(result['valid'])
        self.assertIn('duplicate_archive_member', result['issues'])

    def test_unlisted_member_fails(self):
        make_archive(self.archive, self.files)
        with ZipFile(self.archive, 'a', ZIP_DEFLATED) as archive:
            archive.writestr('LibraAI/extra.txt', b'extra')
        result = verify_release_manifest(self.archive)
        self.assertFalse(result['valid'])
        self.assertIn('unlisted_archive_members', result['issues'])

    def test_missing_manifest_fails(self):
        with ZipFile(self.archive, 'w') as archive:
            archive.writestr('LibraAI/app.py', b'hello')
        result = verify_release_manifest(self.archive)
        self.assertFalse(result['valid'])
        self.assertIn('manifest_missing_or_duplicated', result['issues'])

    def test_malformed_manifest_fails(self):
        make_archive(self.archive, self.files, b'not a valid manifest line\n')
        result = verify_release_manifest(self.archive)
        self.assertFalse(result['valid'])
        self.assertTrue(any(i.startswith('invalid_manifest_line') for i in result['issues']))

    def test_path_traversal_in_manifest_fails(self):
        bad = (hashlib.sha256(b'x').hexdigest() + '  LibraAI/../outside.txt\n').encode()
        make_archive(self.archive, self.files, bad)
        result = verify_release_manifest(self.archive)
        self.assertFalse(result['valid'])
        self.assertTrue(any(i.startswith('unsafe_or_duplicate_manifest_path') for i in result['issues']))

    def test_hash_mismatch_fails(self):
        bad = ('0' * 64 + '  LibraAI/app.py\n' +
               hashlib.sha256(self.files['LibraAI/README.md']).hexdigest() + '  LibraAI/README.md\n').encode()
        make_archive(self.archive, self.files, bad)
        result = verify_release_manifest(self.archive)
        self.assertFalse(result['valid'])
        self.assertIn('hash_mismatch:LibraAI/app.py', result['issues'])

    def test_corrupt_non_zip_fails_cleanly(self):
        self.archive.write_bytes(b'not a zip')
        result = verify_release_manifest(self.archive)
        self.assertFalse(result['valid'])
        self.assertIn('invalid_or_corrupt_archive', result['issues'])

if __name__ == '__main__':
    unittest.main()
