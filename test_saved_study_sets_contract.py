"""Dependency-free contract tests for durable study-set workflow and bilingual analysis."""
from pathlib import Path
import unittest
from study_tools import generate_study_set

ROOT = Path(__file__).resolve().parent
APP = (ROOT / 'app.py').read_text(encoding='utf-8')
UI = (ROOT / 'frontend' / 'app' / 'study-tools' / 'page.tsx').read_text(encoding='utf-8')


class StudySetWorkflowTests(unittest.TestCase):
    def test_english_text_generates_summary_quiz_and_flashcards(self):
        source = (
            'Photosynthesis allows plants to convert light energy into chemical energy. '
            'Chlorophyll absorbs sunlight and supports the process of photosynthesis. '
            'Plants use water and carbon dioxide to produce sugars and release oxygen. '
            'This process supports ecosystems and provides energy for many living organisms.'
        )
        result = generate_study_set(source)
        self.assertEqual(result['mode'], 'local-extractive')
        self.assertTrue(result['summary'])
        self.assertTrue(result['keywords'])
        self.assertTrue(result['quiz'])
        self.assertTrue(result['flashcards'])

    def test_bengali_text_generates_keywords_and_bengali_flashcard_prompts(self):
        source = (
            'সালোকসংশ্লেষণ প্রক্রিয়ায় উদ্ভিদ সূর্যের আলো ব্যবহার করে খাদ্য তৈরি করে। '
            'ক্লোরোফিল পাতার মধ্যে আলো শোষণ করে এবং এই প্রক্রিয়াকে কার্যকর করে। '
            'উদ্ভিদ পানি ও কার্বন ডাই অক্সাইড ব্যবহার করে শর্করা তৈরি করে এবং অক্সিজেন ছাড়ে। '
            'এই প্রক্রিয়া পরিবেশের ভারসাম্য বজায় রাখে এবং জীবজগতকে শক্তি সরবরাহ করে।'
        )
        result = generate_study_set(source)
        self.assertTrue(result['keywords'])
        self.assertTrue(result['flashcards'])
        self.assertTrue(any('এই অধ্যায়ে' in card['front'] for card in result['flashcards']))
        self.assertTrue(result['quiz'])

    def test_input_limits_and_sentence_validation(self):
        with self.assertRaises(ValueError):
            generate_study_set('too short')
        with self.assertRaises(ValueError):
            generate_study_set('x' * 20001)

    def test_account_scoped_persistence_endpoints_and_schema_exist(self):
        for marker in (
            'CREATE TABLE IF NOT EXISTS saved_study_sets',
            "@app.get('/api/study-tools/saved')",
            "@app.get('/api/study-tools/saved/<int:set_id>')",
            "@app.delete('/api/study-tools/saved/<int:set_id>')",
            'WHERE id=? AND user_id=?',
            "'INSERT INTO saved_study_sets(user_id,title,result_json) VALUES(?,?,?)'",
        ):
            self.assertIn(marker, APP)

    def test_ui_supports_save_open_delete_workflow(self):
        for marker in ('saveCurrentSet', 'openSavedSet', 'deleteSavedSet', 'YOUR STUDY LIBRARY', 'Save to my library'):
            self.assertIn(marker, UI)


if __name__ == '__main__':
    unittest.main()
