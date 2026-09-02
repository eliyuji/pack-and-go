import unittest

from backend.query_parse import extract_city, extract_query_locations


class ExtractCityTests(unittest.TestCase):
    def test_taipei_with_trailing_vibe(self):
        self.assertEqual(
            extract_city("3-day trip in Taipei focused on food"),
            "Taipei",
        )

    def test_to_paris(self):
        self.assertEqual(extract_city("3-day trip to Paris"), "Paris")

    def test_nyc_alias(self):
        self.assertEqual(extract_city("weekend in NYC"), "New York")

    def test_old_split_would_have_failed(self):
        bogus = "3-day trip in Taipei focused on food".split(" in ")[-1].strip().title()
        self.assertEqual(bogus, "Taipei Focused On Food")
        self.assertEqual(extract_city("3-day trip in Taipei focused on food"), "Taipei")

    def test_empty(self):
        self.assertIsNone(extract_city(""))
        self.assertIsNone(extract_city("   "))


class ExtractQueryLocationsTests(unittest.TestCase):
    def test_includes_canonical_city(self):
        locs = [loc.lower() for loc in extract_query_locations("food in Taipei")]
        self.assertIn("taipei", locs)


if __name__ == "__main__":
    unittest.main()
