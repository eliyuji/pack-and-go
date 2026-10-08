"""Match itinerary activity text to a place row, then rank places by distance.

Pure functions over plain dicts: no SQLite, Groq, or FAISS imports, so this is
cheap to unit test.
"""

from __future__ import annotations

import re
from collections import Counter
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0

# Words too generic to identify a venue on their own. "Tainan Museum" should not
# match every museum in the city off the back of "museum".
GENERIC_TOKENS = {
    "and", "the", "for", "with", "your", "then", "from", "into", "near",
    "visit", "tour", "explore", "stroll", "walk", "walking", "enjoy", "sample",
    "morning", "afternoon", "evening", "day", "trip", "local", "traditional",
    "historical", "scenic", "views", "area", "old", "new", "city", "town",
    "district", "street", "road", "market", "night", "museum", "temple",
    "park", "garden", "shrine", "fort", "hall", "center", "centre", "square",
    "cafe", "coffee", "bar", "house", "shop", "store", "mall", "art", "arts",
    "space", "park", "station", "tower", "bridge", "river", "lake", "mountain",
    "food", "snacks", "delicacies", "cuisine", "restaurant", "branch", "store",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_CJK_RE = re.compile(r"[\u3400-\u9fff]{2,}")

# City-wide names that show up as leftover district rows or in every activity.
_CITY_STEMS = {
    "tainan",
    "taipei",
    "taichung",
    "bangkok",
    "paris",
    "tokyo",
    "bali",
    "peninsula",
    "bay",
}

# Well-known spots whose district is not in the activity text. Only districts
# we actually dump. Chimei is in Rende; East is the closest row we have.
LANDMARK_DISTRICTS = {
    "chimei": "East District",
    "fine arts": "West Central District",
    "art museum": "West Central District",
    "chihkan": "West Central District",
    "chikan": "West Central District",
    "fort provintia": "West Central District",
    "confucius": "West Central District",
    "city god": "West Central District",
    "hayashi": "West Central District",
    "shennong": "West Central District",
    "blueprint": "West Central District",
    "garden night market": "North District",
    "flower night market": "North District",
    "yanshui": "North District",
    "hutoupi": "East District",
    "tree valley": "Yongkang District",
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(h))


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _distinctive(tokens: set[str]) -> set[str]:
    return {t for t in tokens if len(t) > 3 and t not in GENERIC_TOKENS}


def match_score(activity_text: str, place_name: str) -> float:
    """0..1 confidence that `activity_text` refers to `place_name`."""
    if not activity_text or not place_name:
        return 0.0

    activity_low = activity_text.lower()

    # Chinese names have no spaces, so a substring hit is already strong.
    for run in _CJK_RE.findall(place_name):
        if run in activity_text:
            return 1.0

    place_tokens = _tokens(place_name)
    if not place_tokens:
        return 0.0

    activity_tokens = _tokens(activity_low)
    overlap = place_tokens & activity_tokens
    if not overlap:
        return 0.0

    # Require at least one non-generic word in common, otherwise "Fine Arts
    # Museum" matches any museum.
    if not _distinctive(overlap):
        return 0.0

    return len(overlap) / len(place_tokens)


def match_place(activity_text: str, places: list, threshold: float = 0.6):
    """Best-matching place for an activity, or None when nothing is confident."""
    best, best_score = None, 0.0
    for place in places or []:
        if place.get("lat") is None or place.get("lon") is None:
            continue
        score = match_score(activity_text, place.get("name") or "")
        # Tie-break on the longer name: "Anping Old Fort" beats "Anping".
        if score > best_score or (
            score == best_score
            and best is not None
            and len(place.get("name") or "") > len(best.get("name") or "")
        ):
            if score >= threshold:
                best, best_score = place, score
    return best


def sort_by_distance(places: list, lat: float, lon: float) -> list:
    """Places that have coordinates, nearest first."""
    located = [
        p for p in places if p.get("lat") is not None and p.get("lon") is not None
    ]
    return sorted(
        located, key=lambda p: haversine_km(lat, lon, float(p["lat"]), float(p["lon"]))
    )


def district_from_text(act_text: str, districts: list[str]) -> str | None:
    """District named in the activity, or a known landmark's district."""
    act_low = (act_text or "").lower()
    if not act_low:
        return None

    known = {d for d in districts if d}
    # Longest stem first so "West Central" wins over a hypothetical "West".
    for district in sorted(known, key=len, reverse=True):
        stem = district.lower().replace(" district", "").strip()
        if not stem or stem in _CITY_STEMS:
            continue
        if re.search(rf"\b{re.escape(stem)}\b", act_low):
            return district

    for needle, district in LANDMARK_DISTRICTS.items():
        if needle in act_low and district in known:
            return district
    return None


def next_spread_district(districts: list[str], used: Counter) -> str | None:
    """Least-used district so unmatched slots do not all pile into Anping."""
    names = [d for d in districts if d]
    if not names:
        return None
    return min(names, key=lambda d: (used.get(d, 0), names.index(d)))
