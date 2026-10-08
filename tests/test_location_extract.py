import os
import unittest
from unittest.mock import patch


class HybridLocationTests(unittest.TestCase):
    def test_skips_flan_when_spacy_finds_nothing(self):
        os.environ.pop("INDEX_USE_FLAN", None)
        from semantic_search import extract_locations_hybrid

        cache = {}
        with patch("semantic_search.get_locations_spacy", return_value=[]):
            results = extract_locations_hybrid(["no place names here"], cache, "demo.txt")

        self.assertEqual(results, [[]])
        self.assertTrue(any(v == [] for v in cache.values()))
