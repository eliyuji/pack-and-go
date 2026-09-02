"""Parse a trip query into a city name. No FAISS / Groq imports."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

# Canonical names should match Places SQLite (`cities.name`) when the city exists.
CITY_ALIASES = {
    "taipei": "Taipei",
    "bangkok": "Bangkok",
    "paris": "Paris",
    "tokyo": "Tokyo",
    "bali": "Bali",
    "new york": "New York",
    "new york city": "New York",
    "nyc": "New York",
    "hong kong": "Hong Kong",
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


def places_for_query(query: str) -> list:
    from backend.database.attraction_query import get_places_for_city

    city = extract_city(query)
    if not city:
        return []
    return get_places_for_city(city)
