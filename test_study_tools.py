import unittest
from study_tools import generate_study_set

SAMPLE = (
    "Photosynthesis allows green plants to convert sunlight into chemical energy. "
    "Chlorophyll absorbs light and helps drive the process inside plant cells. "
    "Plants use carbon dioxide and water to produce glucose and release oxygen. "
    "This process supports most food chains and helps maintain atmospheric balance. "
) * 2

class StudyToolsTests(unittest.TestCase):
    def test_generates_summary_quiz_and_flashcards(self):
        result = generate_study_set(SAMPLE)
        self.assertEqual(result['mode'], 'local-extractive')
        self.assertTrue(result['summary'])
        self.assertTrue(result['keywords'])
        self.assertTrue(result['quiz'])
        self.assertTrue(result['flashcards'])
        self.assertLessEqual(len(result['summary']), 1800)

    def test_rejects_too_short_text(self):
        with self.assertRaises(ValueError):
            generate_study_set('Too short.')

    def test_rejects_text_over_limit(self):
        with self.assertRaises(ValueError):
            generate_study_set('x' * 20001)

    def test_requires_multiple_sentences(self):
        with self.assertRaises(ValueError):
            generate_study_set('This is a single long sentence that is long enough to pass the initial character limit but has no second sentence.')

if __name__ == '__main__':
    unittest.main()
