import argparse
import os
import time
import requests

import backend.env  # noqa: F401
from backend.database.db_schema import Session, City, District, Place

session = Session()

CATEGORIES = {
    "attraction": [
        "tourist attraction",
        "museum",
        "temple",
        "landmark",
        "historical site",
        "market",
        "zoo",
        "observation deck",
        "art gallery",
        "garden",
        "park",
        "hiking trail",
        "nature preserve",
        "farmers market",
        "historic downtown",
    ],
    "restaurant": [
        "restaurant",
        "cafe",
        "street food",
        "tea house",
        "ramen",
        "dim sum",
        "bubble tea",
        "brunch",
        "vegetarian food",
        "barbecue",
        "dessert cafe",
    ],
    "nightlife": [
        "bar",
        "night club",
        "live music",
        "karaoke",
        "speakeasy",
        "rooftop bar",
        "lounge",
        "pub",
        "beer hall",
        "night market",
    ],
}

CITY_DISTRICTS = {
    "Taipei": [
        "Zhongzheng District",
        "Datong District",
        "Zhongshan District",
        "Songshan District",
        "Da’an District",
        "Wanhua District",
        "Xinyi District",
        "Shilin District",
        "Beitou District",
        "Neihu District",
        "Nangang District",
        "Wenshan District",
    ],
    "Tainan": [
        "Anping District",
        "West Central District",
        "East District",
        "North District",
        "South District",
        "Yongkang District",
    ],
    "Taichung": [
        "Central District",
        "West District",
        "Xitun District",
        "Nantun District",
        "North District",
        "Beitun District",
        "Fengyuan District",
    ],
    # Towns as districts so "weekend in Palo Alto" shares one Places dump.
    "Peninsula": [
        "San Mateo",
        "San Carlos",
        "Redwood City",
        "Menlo Park",
        "Palo Alto",
        "Milpitas",
        "Fremont",
    ],
}

# Text Search is better as "park in Palo Alto, California" than "... Peninsula".
CITY_QUERY_REGION = {
    "Peninsula": "California",
}


def _require_places_key() -> str:
    for name in ("GOOGLE_API_KEY", "GOOGLE_PLACES", "YOUTUBE_API_KEY"):
        key = (os.getenv(name) or "").strip()
        if key:
            if name == "YOUTUBE_API_KEY":
                print("Using YOUTUBE_API_KEY for Places (GOOGLE_API_KEY is empty).")
            return key
    raise ValueError(
        "GOOGLE_API_KEY is not set in .env. "
        "Enable Places API (Text Search) in Google Cloud and create an API key."
    )


def fetch_places(query, location=None, radius=3000, type=None, max_results=20):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": query, "key": _require_places_key(), "radius": radius}
    if location:
        params["location"] = location
    if type:
        params["type"] = type

    results = []
    while len(results) < max_results:
        resp = requests.get(url, params=params)
        data = resp.json()
        status = data.get("status")
        if status not in ("OK", "ZERO_RESULTS"):
            message = data.get("error_message", status)
            raise RuntimeError(f"Places API error for '{query}': {message}")
        results.extend(data.get("results", []))
        if "next_page_token" not in data or len(results) >= max_results:
            break
        time.sleep(2)
        params["pagetoken"] = data["next_page_token"]
    return results[:max_results]


def populate_city(city_name):
    print(f"Populating data for {city_name}...")
    city = session.query(City).filter_by(name=city_name).first()
    if not city:
        city = City(name=city_name)
        session.add(city)
        session.commit()

    districts = CITY_DISTRICTS.get(city_name) or [city_name]

    for district_name in districts:
        district = (
            session.query(District)
            .filter_by(name=district_name, city_id=city.id)
            .first()
        )
        if not district:
            district = District(name=district_name, city_id=city.id)
            session.add(district)
            session.commit()

        for category, google_types in CATEGORIES.items():
            for gtype in google_types:
                region = CITY_QUERY_REGION.get(city_name, city_name)
                query = f"{gtype} in {district_name}, {region}"
                print(f"Fetching {query}...")
                results = fetch_places(query, max_results=10)
                for r in results:
                    place_id = r.get("place_id")
                    if not place_id:
                        continue
                    existing = session.query(Place).filter_by(place_id=place_id).first()
                    if existing:
                        continue
                    geometry = r.get("geometry", {}).get("location", {})
                    place = Place(
                        name=r["name"],
                        address=r.get("formatted_address", ""),
                        rating=r.get("rating", 0),
                        category=category,
                        district_id=district.id,
                        place_id=place_id,
                        lat=geometry.get("lat"),
                        lon=geometry.get("lng"),
                    )
                    session.add(place)
                session.commit()
    print(f"Done populating {city_name}!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch Google Places into the local SQLite travel_data.db."
    )
    parser.add_argument(
        "cities",
        nargs="+",
        help="City names from CITY_DISTRICTS (Taipei, Tainan, Taichung, Peninsula). "
        "Unknown names are searched as a single region. Always pass names explicitly "
        "so a no-arg run cannot re-dump every city.",
    )
    args = parser.parse_args()
    for city in args.cities:
        populate_city(city)
