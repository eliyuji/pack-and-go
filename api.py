import os
import requests
GOOGLE_PLACES = os.getenv("GOOGLE_PLACES")

def fetch_places_from_api(region, query_type="restaurant", limit=5):
    """Fetches real-world places based on a region and query type."""
    if not GOOGLE_PLACES:
        print("⚠️ GOOGLE_PLACES_API_KEY not set. Skipping API call.")
        return []

    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": f"{query_type} in {region}",
        "key": GOOGLE_PLACES
    }

    response = requests.get(url, params=params)
    data = response.json()

    if "results" not in data:
        print(f"⚠️ No results found for {region}")
        return []

    places = []
    for place in data["results"][:limit]:
        name = place.get("name", "Unknown")
        address = place.get("formatted_address", "Address unavailable")
        rating = place.get("rating", "N/A")
        places.append(f"{name} ({rating}⭐) - {address}")

    print(f"✅ Retrieved {len(places)} {query_type}(s) for {region}")
    return places