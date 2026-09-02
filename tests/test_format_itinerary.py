import unittest

from rag_pipeline import format_itinerary, normalize_activity_times


class FormatByStructuredTimeTests(unittest.TestCase):
    def test_night_market_stays_in_morning_if_time_is_morning(self):
        activities = [
            {
                "time": "Morning",
                "activity": "Raohe Night Market breakfast crawl",
                "food": "Pepper buns",
            }
        ]
        text = format_itinerary(activities)
        morning = text.split("☀️ Afternoon:")[0]
        self.assertIn("Raohe Night Market", morning)
        self.assertIn("☀️ Morning:", text)
        self.assertNotIn("☀️ Evening:", text)

    def test_missing_time_falls_back_to_keywords(self):
        activities = [
            {"activity": "Raohe Night Market", "food": "Pepper buns"},
        ]
        text = format_itinerary(activities)
        self.assertIn("☀️ Evening:", text)
        self.assertIn("Raohe Night Market", text)


class NormalizeFillsMissingOnlyTests(unittest.TestCase):
    def test_does_not_move_explicit_morning_night_market(self):
        itinerary = {
            "itinerary": [
                {
                    "day": 2,
                    "activities": [
                        {
                            "time": "Morning",
                            "activity": "Raohe Night Market",
                            "food": "Pepper buns",
                        }
                    ],
                }
            ]
        }
        updated = normalize_activity_times(itinerary)
        self.assertEqual(updated["itinerary"][0]["activities"][0]["time"], "Morning")

    def test_fills_missing_time(self):
        itinerary = {
            "itinerary": [
                {
                    "day": 1,
                    "activities": [{"activity": "Visit a museum", "food": "Cafe"}],
                }
            ]
        }
        updated = normalize_activity_times(itinerary)
        self.assertEqual(updated["itinerary"][0]["activities"][0]["time"], "Morning")


if __name__ == "__main__":
    unittest.main()
