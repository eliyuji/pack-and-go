"""Fill missing Place lat/lon from Google Place Details. Persist so we do not refetch."""

from __future__ import annotations

import os

import backend.env  # noqa: F401
from backend.database.db_schema import Place, Session

_CACHE: dict[str, tuple[float, float]] = {}


def _api_key() -> str:
    return (os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_PLACES") or "").strip()


def _lookup_details(place_id: str) -> tuple[float, float] | None:
    if place_id in _CACHE:
        return _CACHE[place_id]
    key = _api_key()
    if not key:
        return None
    try:
        import requests

        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params={"place_id": place_id, "fields": "geometry", "key": key},
            timeout=12,
        )
        data = resp.json()
        loc = (data.get("result") or {}).get("geometry", {}).get("location") or {}
        lat, lon = loc.get("lat"), loc.get("lng")
        if lat is None or lon is None:
            return None
        coords = (float(lat), float(lon))
        _CACHE[place_id] = coords
        return coords
    except Exception:
        return None


def _persist(place_id: str, lat: float, lon: float) -> None:
    session = Session()
    try:
        row = session.query(Place).filter_by(place_id=place_id).first()
        if not row:
            return
        row.lat = lat
        row.lon = lon
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def fill_itinerary_coords(itinerary: dict) -> dict:
    """Walk every place and food option and fill missing lat/lon in place."""
    for day in itinerary.get("itinerary") or []:
        for activity in day.get("activities") or []:
            place = activity.get("place")
            if isinstance(place, dict):
                activity["place"] = fill_missing_coords(place)
            options = activity.get("food_options") or []
            activity["food_options"] = [
                fill_missing_coords(option) if isinstance(option, dict) else option
                for option in options
            ]
    return itinerary


def fill_missing_coords(place: dict) -> dict:
    """Return a copy with lat/lon filled when the SQLite row was saved without them."""
    if place.get("lat") is not None and place.get("lon") is not None:
        return place
    place_id = place.get("place_id")
    if not place_id:
        return place
    coords = _lookup_details(place_id)
    if not coords:
        return place
    lat, lon = coords
    _persist(place_id, lat, lon)
    filled = dict(place)
    filled["lat"] = lat
    filled["lon"] = lon
    return filled
