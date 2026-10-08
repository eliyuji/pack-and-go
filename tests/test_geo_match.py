import unittest

from collections import Counter

from backend.geo_match import (
    district_from_text,
    haversine_km,
    match_place,
    match_score,
    next_spread_district,
    sort_by_distance,
)

ANPING_FORT = {"name": "Anping Old Fort", "lat": 23.0013, "lon": 120.1605}
CHIMEI = {"name": "Chimei Museum", "lat": 22.9165, "lon": 120.2764}
FINE_ARTS = {"name": "Tainan Art Museum Building 2", "lat": 22.9885, "lon": 120.2016}
CHINESE = {"name": "螺旋天幕廣場", "lat": 22.97, "lon": 120.22}
NO_COORDS = {"name": "Ghost Venue", "lat": None, "lon": None}

PLACES = [ANPING_FORT, CHIMEI, FINE_ARTS, CHINESE, NO_COORDS]


class HaversineTests(unittest.TestCase):
    def test_zero_distance(self):
        self.assertAlmostEqual(haversine_km(23.0, 120.0, 23.0, 120.0), 0.0)

    def test_known_short_hop(self):
        # Anping Fort to Chimei Museum is roughly 15 km apart.
        km = haversine_km(23.0013, 120.1605, 22.9165, 120.2764)
        self.assertTrue(14 < km < 18, km)


class MatchScoreTests(unittest.TestCase):
    def test_generic_word_alone_does_not_match(self):
        self.assertEqual(match_score("Tour a museum downtown", "Chimei Museum"), 0.0)

    def test_distinctive_word_matches(self):
        self.assertGreater(match_score("Visit Chimei Museum", "Chimei Museum"), 0.9)

    def test_chinese_substring_matches(self):
        self.assertEqual(match_score("Visit 螺旋天幕廣場 for art", "螺旋天幕廣場"), 1.0)

    def test_empty_inputs(self):
        self.assertEqual(match_score("", "Chimei Museum"), 0.0)
        self.assertEqual(match_score("Visit Chimei Museum", ""), 0.0)


class MatchPlaceTests(unittest.TestCase):
    def test_finds_anping_fort(self):
        got = match_place("Historical walking tour starting at Anping Old Fort", PLACES)
        self.assertEqual(got["name"], "Anping Old Fort")

    def test_unrelated_activity_returns_none(self):
        self.assertIsNone(match_place("Relax at the hotel pool", PLACES))

    def test_generic_museum_activity_returns_none(self):
        self.assertIsNone(match_place("Visit a museum and a temple", PLACES))

    def test_skips_places_without_coordinates(self):
        self.assertIsNone(match_place("Ghost Venue tour", PLACES))


class DistrictFromTextTests(unittest.TestCase):
    DISTRICTS = [
        "Anping District",
        "West Central District",
        "East District",
        "Tainan",
    ]

    def test_named_district(self):
        self.assertEqual(
            district_from_text("Stroll Anping Old Street", self.DISTRICTS),
            "Anping District",
        )

    def test_landmark_not_in_anping(self):
        self.assertEqual(
            district_from_text("Tour National Tainan Museum of Fine Arts", self.DISTRICTS),
            "West Central District",
        )

    def test_city_name_is_not_a_district(self):
        self.assertIsNone(district_from_text("A day in Tainan", self.DISTRICTS))

    def test_unmatched(self):
        self.assertIsNone(district_from_text("Hotel spa afternoon", self.DISTRICTS))


class SpreadDistrictTests(unittest.TestCase):
    def test_picks_least_used(self):
        districts = ["Anping District", "East District"]
        used = Counter({"Anping District": 3})
        self.assertEqual(next_spread_district(districts, used), "East District")


class SortByDistanceTests(unittest.TestCase):
    def test_nearest_first_and_drops_uncoordinated(self):
        ordered = sort_by_distance(PLACES, ANPING_FORT["lat"], ANPING_FORT["lon"])
        self.assertEqual(ordered[0]["name"], "Anping Old Fort")
        self.assertNotIn("Ghost Venue", [p["name"] for p in ordered])


if __name__ == "__main__":
    unittest.main()
