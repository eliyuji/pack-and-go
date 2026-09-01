import os
import requests
import backend.env  # noqa: F401

GOOGLE_PLACES = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_PLACES")

def fetch_places_from_api(region, query_type="restaurant", limit=5):
    """Fetches real-world places based on a region and query type."""
    if not GOOGLE_PLACES:
        print("GOOGLE_API_KEY is not set. Skipping Places API call.")
        return []

    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": f"{query_type} in {region}",
        "key": GOOGLE_PLACES,
    }

    response = requests.get(url, params=params)
    data = response.json()

    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        print(f"Places API error: {data.get('error_message', data.get('status'))}")
        return []

    if "results" not in data:
        print(f"No results found for {region}")
        return []

    places = []
    for place in data["results"][:limit]:
        name = place.get("name", "Unknown")
        address = place.get("formatted_address", "Address unavailable")
        rating = place.get("rating", "N/A")
        places.append(f"{name} ({rating}⭐) - {address}")

    print(f"Retrieved {len(places)} {query_type}(s) for {region}")
    return places
