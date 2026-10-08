import unittest

from backend.query_parse import (
    extract_city,
    extract_query_locations,
    merge_source_ids,
    youtube_ids_from_filenames,
)


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

    def test_tainan_alias(self):
        self.assertEqual(extract_city("3-day trip in Tainan focused on food"), "Tainan")

    def test_old_split_would_have_failed(self):
        bogus = "3-day trip in Taipei focused on food".split(" in ")[-1].strip().title()
        self.assertEqual(bogus, "Taipei Focused On Food")
        self.assertEqual(extract_city("3-day trip in Taipei focused on food"), "Taipei")

    def test_empty(self):
        self.assertIsNone(extract_city(""))
        self.assertIsNone(extract_city("   "))

    def test_peninsula_aliases(self):
        self.assertEqual(extract_city("weekend in Palo Alto"), "Peninsula")
        self.assertEqual(
            extract_city("3-day trip on the Peninsula focused on parks"), "Peninsula"
        )
        self.assertEqual(extract_city("day trip in the Bay Area"), "Peninsula")
        self.assertEqual(extract_city("hike in Redwood City"), "Peninsula")
        self.assertEqual(extract_city("parks in Fremont"), "Peninsula")


class YoutubeIdTests(unittest.TestCase):
    def test_strips_txt_and_dedupes(self):
        self.assertEqual(
            youtube_ids_from_filenames(
                ["0vy50-De12s.txt", "folder/0vy50-De12s.txt", "abcDEF12345.txt"]
            ),
            ["0vy50-De12s", "abcDEF12345"],
        )

    def test_merge_keeps_order_and_cap(self):
        self.assertEqual(
            merge_source_ids(["a", "b"], ["b", "c"], ["d"]),
            ["a", "b", "c", "d"],
        )


class ExtractQueryLocationsTests(unittest.TestCase):
    def test_includes_canonical_city(self):
        locs = [loc.lower() for loc in extract_query_locations("food in Taipei")]
        self.assertIn("taipei", locs)


if __name__ == "__main__":
    unittest.main()
