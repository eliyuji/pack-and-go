import unittest

from backend.itinerary_patch import patch_activity
from rag_pipeline import ensure_food, maps_url
from backend.database.place_coords import fill_itinerary_coords, fill_missing_coords


def place(name, district, category="restaurant", lat=25.0, lon=121.5):
    return {
        "name": name,
        "district": district,
        "category": category,
        "rating": 4.5,
        "address": f"{name} address",
        "lat": lat,
        "lon": lon,
        "place_id": f"pid-{name}",
    }


PLACES = [
    place("Anping Eats", "Anping District"),
    place("Anping Noodles", "Anping District"),
    place("Anping Buns", "Anping District"),
    place("East Cafe", "East District"),
    place("East Grill", "East District"),
    place("Old Fort", "Anping District", category="attraction"),
]


def itinerary_with(activity, food=None):
    slot = {"time": "Morning", "activity": activity}
    if food:
        slot["food"] = food
    return {"itinerary": [{"day": 1, "activities": [slot]}]}


class FoodOptionsTests(unittest.TestCase):
    def test_attaches_three_options(self):
        result = ensure_food(itinerary_with("Visit Anping Old Fort"), PLACES)
        options = result["itinerary"][0]["activities"][0]["food_options"]
        self.assertEqual(len(options), 3)
        self.assertEqual(len({o["name"] for o in options}), 3)

    def test_options_carry_coordinates_and_link(self):
        result = ensure_food(itinerary_with("Visit Anping Old Fort"), PLACES)
        option = result["itinerary"][0]["activities"][0]["food_options"][0]
        for key in ("name", "rating", "lat", "lon", "place_id", "maps_url"):
            self.assertIn(key, option)
        self.assertTrue(option["maps_url"].startswith("https://www.google.com/maps/"))

    def test_fill_itinerary_keeps_food_coordinates(self):
        trip = ensure_food(itinerary_with("Visit Anping Old Fort"), PLACES)
        filled = fill_itinerary_coords(trip)
        option = filled["itinerary"][0]["activities"][0]["food_options"][0]
        self.assertIsNotNone(option["lat"])
        self.assertIsNotNone(option["lon"])

    def test_keeps_existing_coordinates_without_lookup(self):
        original = place("Already Mapped", "Anping District")
        filled = fill_missing_coords(original)
        self.assertEqual(filled["lat"], 25.0)
        self.assertEqual(filled["lon"], 121.5)

    def test_replaces_food_options_that_lack_coordinates(self):
        slot = itinerary_with("Visit Anping Old Fort", food="Shrimp rolls")
        slot["itinerary"][0]["activities"][0]["food_options"] = [
            {"name": "Nameless stall"}
        ]
        result = ensure_food(slot, PLACES)
        option = result["itinerary"][0]["activities"][0]["food_options"][0]
        self.assertIsNotNone(option.get("lat"))
        self.assertIsNotNone(option.get("lon"))

    def test_never_suggests_an_attraction_as_food(self):
        result = ensure_food(itinerary_with("Visit Anping Old Fort"), PLACES)
        names = {o["name"] for o in result["itinerary"][0]["activities"][0]["food_options"]}
        self.assertNotIn("Old Fort", names)

    def test_keeps_model_food_string(self):
        result = ensure_food(itinerary_with("Anping walk", food="Shrimp rolls"), PLACES)
        activity = result["itinerary"][0]["activities"][0]
        self.assertEqual(activity["food"], "Shrimp rolls")
        self.assertEqual(len(activity["food_options"]), 3)

    def test_no_restaurants_is_not_an_error(self):
        result = ensure_food(itinerary_with("Anping walk"), [])
        activity = result["itinerary"][0]["activities"][0]
        self.assertEqual(activity["food"], "unknown")
        self.assertEqual(activity["food_options"], [])

    def test_prefers_matching_district(self):
        result = ensure_food(itinerary_with("Stroll Anping District"), PLACES)
        options = result["itinerary"][0]["activities"][0]["food_options"]
        self.assertTrue(all(o["district"] == "Anping District" for o in options))

    def test_fine_arts_is_not_anping_food(self):
        places = PLACES + [
            place("Hayashi Cafe", "West Central District"),
            place("Shennong Noodles", "West Central District"),
            place("Chihkan Tea", "West Central District"),
        ]
        result = ensure_food(
            itinerary_with("Tour National Tainan Museum of Fine Arts"), places
        )
        districts = {
            o["district"]
            for o in result["itinerary"][0]["activities"][0]["food_options"]
        }
        self.assertEqual(districts, {"West Central District"})

    def test_unmatched_slots_rotate_districts(self):
        places = [place(f"Anping {i}", "Anping District") for i in range(6)] + [
            place(f"East {i}", "East District") for i in range(6)
        ]
        itinerary = {
            "itinerary": [
                {
                    "day": 1,
                    "activities": [
                        {"time": "Morning", "activity": "Hotel spa morning"},
                        {"time": "Afternoon", "activity": "Hotel spa afternoon"},
                    ],
                }
            ]
        }
        result = ensure_food(itinerary, places)
        first = {
            o["district"]
            for o in result["itinerary"][0]["activities"][0]["food_options"]
        }
        second = {
            o["district"]
            for o in result["itinerary"][0]["activities"][1]["food_options"]
        }
        self.assertNotEqual(first, second)

    def test_maps_url_includes_place_id(self):
        url = maps_url({"name": "Anping Eats", "place_id": "pid-123"})
        self.assertIn("query_place_id=pid-123", url)


class NoRepeatsWithinADayTests(unittest.TestCase):
    def setUp(self):
        self.places = [
            place(f"Anping {i}", "Anping District") for i in range(12)
        ] + [place(f"East {i}", "East District") for i in range(12)]

    def three_anping_slots(self):
        return {
            "itinerary": [
                {
                    "day": 1,
                    "activities": [
                        {"time": "Morning", "activity": "Anping District walk"},
                        {"time": "Afternoon", "activity": "Anping District museum"},
                        {"time": "Evening", "activity": "Anping District market"},
                    ],
                }
            ]
        }

    def test_slots_do_not_share_restaurants(self):
        result = ensure_food(self.three_anping_slots(), self.places)
        names = [
            option["name"]
            for activity in result["itinerary"][0]["activities"]
            for option in activity["food_options"]
        ]
        self.assertEqual(len(names), 9)
        self.assertEqual(len(set(names)), 9)

    def test_falls_back_to_reuse_when_city_is_small(self):
        tiny = [place(f"Only {i}", "Anping District") for i in range(4)]
        result = ensure_food(self.three_anping_slots(), tiny)
        for activity in result["itinerary"][0]["activities"]:
            self.assertEqual(len(activity["food_options"]), 3)


class PlaceholderFoodTests(unittest.TestCase):
    def test_na_is_treated_as_missing(self):
        for placeholder in ("N/A", "n/a", "  ", "none", "TBD"):
            result = ensure_food(
                itinerary_with("Visit Anping Old Fort", food=placeholder), PLACES
            )
            food = result["itinerary"][0]["activities"][0]["food"]
            self.assertNotEqual(food.strip().lower(), placeholder.strip().lower())
            self.assertIn("Anping", food)


class PatchKeepsOptionsInSyncTests(unittest.TestCase):
    def setUp(self):
        self.itinerary = ensure_food(itinerary_with("Visit Anping Old Fort"), PLACES)

    def test_drops_stale_options_when_food_changes(self):
        updated = patch_activity(
            self.itinerary, 1, "Morning", {"activity": "Museum", "food": "Museum cafe"}
        )
        self.assertNotIn("food_options", updated["itinerary"][0]["activities"][0])

    def test_keeps_options_when_food_is_unchanged(self):
        updated = patch_activity(self.itinerary, 1, "Morning", {"activity": "Museum"})
        activity = updated["itinerary"][0]["activities"][0]
        self.assertEqual(activity["activity"], "Museum")
        self.assertEqual(len(activity["food_options"]), 3)


if __name__ == "__main__":
    unittest.main()
