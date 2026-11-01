"""Tests for optional AI-assisted study generation and safe local fallback."""
import json
import os
import unittest
from unittest.mock import patch, MagicMock
from study_tools import generate_study_set

SOURCE = (
    "Photosynthesis allows plants to convert light energy into chemical energy. "
    "Chlorophyll absorbs sunlight and supports the process of photosynthesis. "
    "Plants use water and carbon dioxide to produce sugars and release oxygen. "
    "This process supports ecosystems and provides energy for many living organisms."
)

class AIStudyGenerationTests(unittest.TestCase):
    def test_local_mode_never_calls_provider(self):
        with patch('study_tools.urllib.request.urlopen') as urlopen:
            result = generate_study_set(SOURCE, mode='local')
        urlopen.assert_not_called()
        self.assertEqual(result['mode'], 'local-extractive')

    def test_configured_provider_returns_structured_ai_materials(self):
        body = {'choices': [{'message': {'content': json.dumps({
            'summary': 'Plants turn light into chemical energy.',
            'keywords': ['photosynthesis', 'chlorophyll', 'oxygen'],
            'quiz': [{'question': 'What absorbs sunlight?', 'answer': 'Chlorophyll', 'type': 'short_answer'}] * 3,
            'flashcards': [{'front': 'What absorbs sunlight?', 'back': 'Chlorophyll absorbs sunlight.'}] * 3,
        })}}]}
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(body).encode()
        with patch.dict(os.environ, {'LIBRAAI_LLM_API_KEY': 'test-key', 'LIBRAAI_LLM_BASE_URL': 'https://example.test/v1', 'LIBRAAI_LLM_MODEL': 'test-model'}, clear=False), patch('study_tools.urllib.request.urlopen', return_value=response) as urlopen:
            result = generate_study_set(SOURCE)
        self.assertEqual(result['mode'], 'ai-assisted')
        self.assertEqual(len(result['quiz']), 3)
        self.assertEqual(len(result['flashcards']), 3)
        urlopen.assert_called_once()

    def test_bad_provider_response_falls_back_with_transparent_notice(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"choices":[]}'
        with patch.dict(os.environ, {'LIBRAAI_LLM_API_KEY': 'test-key', 'LIBRAAI_LLM_BASE_URL': 'https://example.test/v1', 'LIBRAAI_LLM_MODEL': 'test-model'}, clear=False), patch('study_tools.urllib.request.urlopen', return_value=response):
            result = generate_study_set(SOURCE)
        self.assertEqual(result['mode'], 'local-extractive')
        self.assertIn('AI generation was unavailable', result['notice'])

    def test_invalid_generation_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            generate_study_set(SOURCE, mode='remote-untrusted')

if __name__ == '__main__':
    unittest.main()
