import random
import unittest

from backend.database.attraction_query import pick_varied
from backend.query_parse import extract_city


class PickVariedTests(unittest.TestCase):
    def test_returns_all_when_pool_small(self):
        self.assertEqual(pick_varied(["a", "b"], 3), ["a", "b"])

    def test_samples_without_replacement(self):
        pool = list(range(15))
        random.seed(0)
        picked = pick_varied(pool, 3)
        self.assertEqual(len(picked), 3)
        self.assertEqual(len(set(picked)), 3)
        self.assertTrue(set(picked).issubset(set(pool)))

    def test_not_always_the_first_three(self):
        pool = list(range(15))
        random.seed(1)
        first = pick_varied(pool, 3)
        random.seed(2)
        second = pick_varied(pool, 3)
        self.assertNotEqual(first, [0, 1, 2])
        self.assertNotEqual(first, second)


class TaiwanCityAliasTests(unittest.TestCase):
    def test_tainan(self):
        self.assertEqual(extract_city("3-day trip in Tainan focused on food"), "Tainan")

    def test_taichung(self):
        self.assertEqual(extract_city("weekend in Taichung"), "Taichung")
