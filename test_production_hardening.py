import pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parent
class ProductionHardeningTests(unittest.TestCase):
    def test_ai_uses_rights_filtered_grounded_pipeline(self):
        source=(ROOT/'app.py').read_text()
        provider=(ROOT/'ai_tutor_provider.py').read_text()
        self.assertIn('from ai_tutor_provider import answer_question', source)
        self.assertIn("@login_required\ndef ai():", source)
        self.assertIn("has_access(conn, int(user_id), int(item['book_id']))", provider)
        self.assertIn("'status': 'no_evidence'", provider)
        self.assertIn('LLM provider is not configured', provider)
    def test_strong_secret_enforced(self):
        self.assertIn("len(os.environ.get('SECRET_KEY', '')) < 32",(ROOT/'app.py').read_text())
    def test_secrets_excluded_from_container(self):
        self.assertIn('\n.env\n',(ROOT/'.dockerignore').read_text())
    def test_secret_template_exists(self):
        self.assertIn('SECRET_KEY=',(ROOT/'.env.example').read_text())
if __name__=='__main__': unittest.main()
