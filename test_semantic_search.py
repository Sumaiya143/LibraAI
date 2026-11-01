import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from semantic_search import rank_books

BOOKS = [
    {"id": 1, "title": "A Summer of Us", "author": "Mira Noor", "genre": "Romance", "description": "An emotional slow-burn love story with a hopeful ending.", "rating": 4.8},
    {"id": 2, "title": "The Last Clue", "author": "R. Hasan", "genre": "Mystery", "description": "A detective investigates a hidden crime and suspicious clues.", "rating": 4.5},
    {"id": 3, "title": "The Dragon Crown", "author": "A. Rahman", "genre": "Fantasy", "description": "Magic, dragons and an ancient kingdom at war.", "rating": 4.7},
]

class SemanticSearchTests(unittest.TestCase):
    def test_natural_language_romance_finds_grounded_catalog_book(self):
        with patch.dict(os.environ, {"LIBRAAI_EMBEDDINGS_API_KEY": "", "OPENAI_API_KEY": ""}):
            result = rank_books("I love emotional slow-burn romance with a hopeful ending", BOOKS)
        self.assertEqual(result["mode"], "local_semantic_fallback")
        self.assertTrue(result["results"])
        self.assertEqual(result["results"][0]["id"], 1)

    def test_mystery_prompt_prefers_mystery_catalog_record(self):
        with patch.dict(os.environ, {"LIBRAAI_EMBEDDINGS_API_KEY": "", "OPENAI_API_KEY": ""}):
            result = rank_books("I want a detective story with crime and clues", BOOKS)
        self.assertTrue(result["results"])
        self.assertEqual(result["results"][0]["id"], 2)


    def test_external_embedding_mode_ranks_and_caches_catalog_vectors(self):
        from semantic_search import rank_books
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            def connect():
                return sqlite3.connect(tmp.name)
            def fake_embeddings(texts):
                vectors = []
                for text in texts:
                    folded = text.casefold()
                    vectors.append([0.0, 1.0] if "mystery" in folded or "clue" in folded else [1.0, 0.0])
                return vectors
            with patch.dict(os.environ, {"LIBRAAI_EMBEDDINGS_API_KEY": "test-key", "OPENAI_API_KEY": ""}), patch("semantic_search._embedding_request", side_effect=fake_embeddings) as provider:
                first = rank_books("romance", BOOKS, connect=connect)
                self.assertEqual(first["mode"], "external_embeddings")
                self.assertEqual(first["results"][0]["id"], 1)
                first_calls = provider.call_count
                second = rank_books("romance", BOOKS, connect=connect)
                self.assertEqual(second["mode"], "external_embeddings")
                # Both catalog vectors and repeated query vectors are cached.
                self.assertEqual(provider.call_count, first_calls)
                cached = connect()
                self.assertEqual(cached.execute("SELECT COUNT(*) FROM semantic_query_embeddings").fetchone()[0], 1)
                cached.close()

    def test_empty_catalog_never_invents_books(self):
        result = rank_books("romance", [])
        self.assertEqual(result["results"], [])

    def test_result_is_limited_to_supplied_catalog(self):
        with patch.dict(os.environ, {"LIBRAAI_EMBEDDINGS_API_KEY": "", "OPENAI_API_KEY": ""}):
            result = rank_books("fantasy dragons", BOOKS, limit=1)
        self.assertLessEqual(len(result["results"]), 1)
        self.assertTrue(all(item["id"] in {1, 2, 3} for item in result["results"]))

if __name__ == "__main__":
    unittest.main()
