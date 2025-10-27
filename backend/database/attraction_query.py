from backend.database.db_schema import Session, City, District, Place
import random

session = Session()

def get_places_for_city(city_name, limit_per_district=3):
    city = session.query(City).filter_by(name=city_name).first()
    if not city:
        return []

    results = []
    for district in city.districts:
        for category in ["attraction", "restaurant", "nightlife"]:
            places = (
                session.query(Place)
                .filter_by(district_id=district.id, category=category)
                .order_by(Place.rating.desc())
                .limit(limit_per_district)
                .all()
            )
            for p in places:
                results.append({
                    "district": district.name,
                    "category": category,
                    "name": p.name,
                    "rating": p.rating
                })
    return results
