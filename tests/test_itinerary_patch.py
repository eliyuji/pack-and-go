import unittest

from backend.itinerary_patch import apply_patches, patch_activity, patch_day


SAMPLE = {
    "itinerary": [
        {
            "day": 1,
            "activities": [
                {"time": "Morning", "activity": "Longshan Temple", "food": "Soy milk"},
                {"time": "Afternoon", "activity": "Taipei 101", "food": "Din Tai Fung"},
                {"time": "Evening", "activity": "Raohe Night Market", "food": "Pepper buns"},
            ],
        },
        {
            "day": 2,
            "activities": [
                {"time": "Morning", "activity": "Shopping in Ximending", "food": "Bubble tea"},
                {"time": "Afternoon", "activity": "Elephant Mountain", "food": "Street snacks"},
                {"time": "Evening", "activity": "Shilin Night Market", "food": "Oyster omelette"},
            ],
        },
    ]
}


class PatchActivityTests(unittest.TestCase):
    def test_replacing_day2_morning_leaves_day1_untouched(self):
        updated = patch_activity(
            SAMPLE,
            day_num=2,
            time_slot="morning",
            new_activity={
                "time": "Morning",
                "activity": "National Palace Museum",
                "food": "Museum cafe",
            },
        )

        day1 = updated["itinerary"][0]
        day2 = updated["itinerary"][1]
        self.assertEqual(day1, SAMPLE["itinerary"][0])
        self.assertEqual(day2["activities"][0]["activity"], "National Palace Museum")
        self.assertEqual(day2["activities"][1]["activity"], "Elephant Mountain")
        self.assertEqual(day2["activities"][2]["activity"], "Shilin Night Market")
        self.assertEqual(
            SAMPLE["itinerary"][1]["activities"][0]["activity"],
            "Shopping in Ximending",
        )

    def test_missing_day_raises(self):
        with self.assertRaises(ValueError):
            patch_activity(SAMPLE, day_num=9, time_slot="Morning", new_activity={"activity": "x"})


class PatchDayTests(unittest.TestCase):
    def test_replacing_day2_leaves_day1_untouched(self):
        new_day = {
            "day": 2,
            "activities": [
                {"time": "Morning", "activity": "Beitou hot springs", "food": "Breakfast"},
                {"time": "Afternoon", "activity": "Yangmingshan", "food": "Tea"},
                {"time": "Evening", "activity": "Tamsui riverside", "food": "A-gei"},
            ],
        }
        updated = patch_day(SAMPLE, day_num=2, new_day=new_day)
        self.assertEqual(updated["itinerary"][0], SAMPLE["itinerary"][0])
        self.assertEqual(updated["itinerary"][1]["activities"][0]["activity"], "Beitou hot springs")


class ApplyPatchesTests(unittest.TestCase):
    def test_only_listed_slots_change(self):
        updated = apply_patches(
            SAMPLE,
            [
                {
                    "day": 2,
                    "time": "Morning",
                    "activity": "National Palace Museum",
                    "food": "Museum cafe",
                }
            ],
        )
        self.assertEqual(updated["itinerary"][0], SAMPLE["itinerary"][0])
        self.assertEqual(
            updated["itinerary"][1]["activities"][0]["activity"],
            "National Palace Museum",
        )
        self.assertEqual(
            updated["itinerary"][1]["activities"][1]["activity"],
            "Elephant Mountain",
        )


if __name__ == "__main__":
    unittest.main()
