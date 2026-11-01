import unittest
from unittest.mock import patch
import ai_tutor_provider as tutor

class TutorProviderTests(unittest.TestCase):
    def test_rejects_empty_or_oversized_question(self):
        with self.assertRaises(ValueError):
            tutor.answer_question('   ')
        with self.assertRaises(ValueError):
            tutor.answer_question('x' * 2001)

    @patch.object(tutor, '_evidence', return_value=[])
    def test_no_matching_evidence_never_invents_answer(self, evidence):
        result = tutor.answer_question('Explain a topic')
        self.assertEqual(result['status'], 'no_evidence')
        self.assertEqual(result['citations'], [])
        self.assertIn('could not find matching passages', result['answer'])

    @patch.object(tutor, '_provider_answer', side_effect=tutor.TutorConfigurationError('not configured'))
    @patch.object(tutor, '_evidence', return_value=[{'document_id': 2, 'title': 'Authorized Sample', 'chunk': 1, 'excerpt': 'Supported evidence.', 'score': 0.7}])
    def test_unconfigured_model_returns_evidence_not_fake_ai(self, evidence, provider):
        result = tutor.answer_question('What is supported?')
        self.assertEqual(result['status'], 'evidence_only')
        self.assertEqual(result['citations'][0]['title'], 'Authorized Sample')
        self.assertIn('no AI-generated answer has been produced', result['answer'])

    @patch.object(tutor, '_provider_answer', return_value='Supported answer [Source 1].')
    @patch.object(tutor, '_evidence', return_value=[{'document_id': 2, 'title': 'Authorized Sample', 'chunk': 1, 'excerpt': 'Supported evidence.', 'score': 0.7}])
    def test_grounded_answer_carries_source_records(self, evidence, provider):
        result = tutor.answer_question('What is supported?')
        self.assertEqual(result['status'], 'grounded_answer')
        self.assertIn('[Source 1]', result['answer'])
        self.assertEqual(len(result['citations']), 1)


    @patch.dict('os.environ', {'LIBRAAI_LLM_API_KEY':'key','LIBRAAI_LLM_BASE_URL':'https://example.invalid/v1','LIBRAAI_LLM_MODEL':'test'})
    @patch('ai_tutor_provider.urllib.request.urlopen')
    def test_provider_rejects_fabricated_source_number(self, open_url):
        import json
        from unittest.mock import MagicMock
        response = MagicMock()
        response.status = 200
        response.read.return_value = json.dumps({'choices':[{'message':{'content':'Unsupported claim [Source 9].'}}]}).encode()
        response.__enter__.return_value = response
        open_url.return_value = response
        with self.assertRaises(tutor.TutorProviderError):
            tutor._provider_answer('question', [{'title':'Book','chunk':1,'document_id':1,'excerpt':'evidence'}])

    @patch.dict('os.environ', {'LIBRAAI_LLM_API_KEY':'key','LIBRAAI_LLM_BASE_URL':'https://example.invalid/v1','LIBRAAI_LLM_MODEL':'test'})
    @patch('ai_tutor_provider.urllib.request.urlopen')
    def test_provider_rejects_uncited_answer(self, open_url):
        import json
        from unittest.mock import MagicMock
        response = MagicMock()
        response.status = 200
        response.read.return_value = json.dumps({'choices':[{'message':{'content':'An uncited claim.'}}]}).encode()
        response.__enter__.return_value = response
        open_url.return_value = response
        with self.assertRaises(tutor.TutorProviderError):
            tutor._provider_answer('question', [{'title':'Book','chunk':1,'document_id':1,'excerpt':'evidence'}])

if __name__ == '__main__':
    unittest.main()
