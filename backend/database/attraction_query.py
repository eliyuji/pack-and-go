from backend.database.db_schema import Session, City, District, Place
import random

session = Session()


def pick_varied(places, k):
    """Sample k items from an already-ranked pool so itineraries are not identical."""
    pool = list(places)
    if len(pool) <= k:
        return pool
    return random.sample(pool, k)


def get_city_places(city_name):
    """Every place in the city, for matching activity text to coordinates."""
    city = session.query(City).filter_by(name=city_name).first()
    if not city:
        return []

    rows = (
        session.query(Place, District.name)
        .join(District, Place.district_id == District.id)
        .filter(District.city_id == city.id)
        .all()
    )
    return [
        {
            "district": district_name,
            "category": p.category,
            "name": p.name,
            "rating": p.rating,
            "address": p.address,
            "lat": p.lat,
            "lon": p.lon,
            "place_id": p.place_id,
        }
        for p, district_name in rows
    ]


def get_places_for_city(city_name, limit_per_district=3, pool_per_district=15):
    city = session.query(City).filter_by(name=city_name).first()
    if not city:
        return []

    results = []
    for district in city.districts:
        for category in ["attraction", "restaurant", "nightlife"]:
            pool = (
                session.query(Place)
                .filter_by(district_id=district.id, category=category)
                .order_by(Place.rating.desc())
                .limit(pool_per_district)
                .all()
            )
            for p in pick_varied(pool, limit_per_district):
                results.append({
                    "district": district.name,
                    "category": category,
                    "name": p.name,
                    "rating": p.rating,
                    "address": p.address,
                    "lat": p.lat,
                    "lon": p.lon,
                    "place_id": p.place_id,
                })
    return results
