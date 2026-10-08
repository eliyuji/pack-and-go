"""Parse a trip query into a city name. No FAISS / Groq imports."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

# Canonical names should match Places SQLite (`cities.name`) when the city exists.
CITY_ALIASES = {
    "taipei": "Taipei",
    "tainan": "Tainan",
    "taichung": "Taichung",
    "bangkok": "Bangkok",
    "paris": "Paris",
    "tokyo": "Tokyo",
    "bali": "Bali",
    "new york": "New York",
    "new york city": "New York",
    "nyc": "New York",
    "hong kong": "Hong Kong",
    "bay area": "Peninsula",
    "peninsula": "Peninsula",
    "san mateo": "Peninsula",
    "san carlos": "Peninsula",
    "redwood city": "Peninsula",
    "menlo park": "Peninsula",
    "palo alto": "Peninsula",
    "milpitas": "Peninsula",
    "fremont": "Peninsula",
}

_ALIAS_PATTERN = re.compile(
    r"\b(" + "|".join(sorted((re.escape(a) for a in CITY_ALIASES), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_IN_TO_PATTERN = re.compile(
    r"\b(?:in|to)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})"
)


@lru_cache(maxsize=1)
def _nlp():
    try:
        import spacy

        return spacy.load("en_core_web_sm")
    except Exception:
        return None


def extract_city(query: str) -> Optional[str]:
    """Best-effort destination. Prefer allowlist, then spaCy, then 'in/to Place'."""
    if not query or not str(query).strip():
        return None
    text = str(query).strip()

    match = _ALIAS_PATTERN.search(text)
    if match:
        return CITY_ALIASES[match.group(1).lower()]

    nlp = _nlp()
    if nlp is not None:
        for ent in nlp(text).ents:
            if ent.label_ in ("GPE", "LOC") and ent.text.strip():
                alias = _ALIAS_PATTERN.search(ent.text)
                if alias:
                    return CITY_ALIASES[alias.group(1).lower()]
                return ent.text.strip()

    place = _IN_TO_PATTERN.search(text)
    if place:
        return place.group(1).strip()
    return None


def extract_query_locations(query: str) -> list[str]:
    """Strings used to boost FAISS hits (matched against chunk text)."""
    if not query:
        return []
    found: list[str] = []
    city = extract_city(query)
    if city:
        found.append(city)
    for m in _ALIAS_PATTERN.finditer(query):
        found.append(m.group(1))
        found.append(CITY_ALIASES[m.group(1).lower()])
    nlp = _nlp()
    if nlp is not None:
        for ent in nlp(query).ents:
            if ent.label_ in ("GPE", "LOC", "FAC") and ent.text.strip():
                found.append(ent.text.strip())
    seen = set()
    unique = []
    for item in found:
        key = item.lower()
        if key in seen or len(key) < 3:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def places_for_query(query: str, **kwargs) -> list:
    from backend.database.attraction_query import get_places_for_city

    city = extract_city(query)
    if not city:
        return []
    return get_places_for_city(city, **kwargs)


def food_places_for_query(query: str) -> list:
    """Wider pool than the prompt list: a day can need 9 distinct restaurants
    in one district, so 3 per district is not enough."""
    return places_for_query(query, limit_per_district=15, pool_per_district=45)


def youtube_ids_from_filenames(names: list | None) -> list[str]:
    """Turn transcript blob names like `abc123.txt` into YouTube video IDs."""
    ids: list[str] = []
    for raw in names or []:
        name = str(raw or "").strip().rsplit("/", 1)[-1]
        if name.endswith(".txt"):
            name = name[:-4]
        if name and name not in ids:
            ids.append(name)
    return ids


def merge_source_ids(*groups: list | None) -> list[str]:
    ids: list[str] = []
    for group in groups:
        for item in group or []:
            if item and item not in ids:
                ids.append(item)
    return ids[:8]


def anchor_places_for_query(query: str) -> list:
    """Every place in the city, used to turn activity text into coordinates."""
    from backend.database.attraction_query import get_city_places

    city = extract_city(query)
    if not city:
        return []
    return get_city_places(city)
