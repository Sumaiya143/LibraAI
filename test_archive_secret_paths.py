import tempfile
import unittest
import zipfile
from pathlib import Path

from archive_release_audit import audit_archive


class ArchiveSecretPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'handoff.zip'

    def audit(self, entries):
        with zipfile.ZipFile(self.path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, value in entries:
                archive.writestr(name, value)
        return audit_archive(self.path)

    def test_rejects_common_developer_credential_files(self):
        for name in ('.npmrc', '.pypirc', '.netrc', 'LibraAI/credentials.txt',
                     'LibraAI/secrets.production.json', 'LibraAI/token.json'):
            with self.subTest(name=name):
                result = self.audit([(name, 'placeholder')])
                self.assertIn('prohibited_entry', result['issues'])

    def test_rejects_cloud_credentials_and_terraform_state(self):
        for name in ('.aws/credentials', '.azure/accessTokens.json',
                     '.config/gcloud/application_default_credentials.json',
                     'infra/terraform.tfstate', 'infra/.terraform/state.json'):
            with self.subTest(name=name):
                result = self.audit([(name, 'placeholder')])
                self.assertIn('prohibited_entry', result['issues'])

    def test_allows_documented_environment_template(self):
        result = self.audit([('LibraAI/.env.example', 'APP_SECRET=replace-me')])
        self.assertTrue(result['safe_for_handoff_review'], result['issues'])


if __name__ == '__main__':
    unittest.main()
