"""Tests for catalog-grounded preference recommendations in the AI chat endpoint."""
import unittest
from unittest.mock import patch
import app


class CatalogRecommendationTests(unittest.TestCase):
    @patch.object(app, 'book_rows')
    def test_romance_preference_prioritizes_matching_catalog_titles(self, rows):
        rows.return_value = [
            {'id': 1, 'title': 'Moonlit Hearts', 'author': 'A. Writer', 'genre': 'Romance', 'rating': 4.8, 'reads': 500, 'description': 'A love story', 'year': 2024, 'sales': 50},
            {'id': 2, 'title': 'Deep Space', 'author': 'B. Writer', 'genre': 'Science Fiction', 'rating': 4.9, 'reads': 900, 'description': 'A space voyage', 'year': 2025, 'sales': 90},
        ]
        result = app._catalog_recommendation('I love romance books, please suggest some')
        self.assertEqual(result['status'], 'catalog_recommendations')
        self.assertEqual(result['recommendations'][0]['title'], 'Moonlit Hearts')
        self.assertIn('/book/1', result['answer'])

    @patch.object(app, 'book_rows', return_value=[])
    def test_empty_catalog_is_reported_without_fabricating_titles(self, _rows):
        result = app._catalog_recommendation('Suggest romance books')
        self.assertIn('could not find books', result['answer'])
        self.assertNotIn('recommendations', result)

    def test_unrelated_question_is_left_for_configured_ai_provider(self):
        self.assertIsNone(app._catalog_recommendation('Explain photosynthesis in simple words'))


if __name__ == '__main__':
    unittest.main()
