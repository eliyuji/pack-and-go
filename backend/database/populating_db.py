import os
import requests
from dotenv import load_dotenv
import time
from db_schema import Session, City, District, Place

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
session = Session()

# 🗺️ Define what you want to fetch
CATEGORIES = {
    "attraction": ["tourist attraction",
        "museum",
        "temple",
        "landmark",
        "historical site",
        "market",
        "zoo",
        "observation deck",
        "art gallery",
        "garden",],
    "restaurant": ["restaurant",
        "cafe",
        "street food",
        "tea house",
        "ramen",
        "dim sum",
        "bubble tea",
        "brunch",
        "vegetarian food",
        "barbecue",
        "dessert cafe",],
    "nightlife": [ "bar",
        "night club",
        "live music",
        "karaoke",
        "speakeasy",
        "rooftop bar",
        "lounge",
        "pub",
        "beer hall",
        "night market",]
}

# 💡 Define which districts belong to which city
# (You’ll probably move this to your DB eventually)
CITY_DISTRICTS = {
    "Taipei": ["Zhongzheng District",
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
        "Wenshan District",],
}

def fetch_places(query, location=None, radius=3000, type=None, max_results=20):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": query, "key": API_KEY, "radius": radius}
    if location:
        params["location"] = location
    if type:
        params["type"] = type

    results = []
    while len(results) < max_results:
        resp = requests.get(url, params=params)
        data = resp.json()
        results.extend(data.get("results", []))
        if "next_page_token" not in data or len(results) >= max_results:
            break
        params["pagetoken"] = data["next_page_token"]
    return results[:max_results]


def populate_city(city_name):
    print(f"🌆 Populating data for {city_name}...")
    city = session.query(City).filter_by(name=city_name).first()
    if not city:
        city = City(name=city_name)
        session.add(city)
        session.commit()

    for district_name in CITY_DISTRICTS.get(city_name, []):
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
                query = f"{gtype} in {district_name}, {city_name}"
                print(f"🔍 Fetching {query}...")
                results = fetch_places(query, max_results=10)
                for r in results:
                    place_id = r.get("place_id")
                    if not place_id:
                        continue
                    name = r["name"]
                    rating = r.get("rating", 0)
                    address = r.get("formatted_address", "")
                    existing = session.query(Place).filter_by(place_id=place_id).first()
                    if not existing:
                        place = Place(
                            name=name,
                            address=address,
                            rating=rating,
                            category=category,
                            district_id=district.id,
                            place_id=place_id,
                        )
                        session.add(place)
                        time.sleep(2)
        session.commit()
    print(f"✅ Done populating {city_name}!")

if __name__ == "__main__":
    for city in CITY_DISTRICTS.keys():
        populate_city(city)
