from groq import Groq
from semantic_search import load_index, retrieve_context
from backend.database.attraction_query import get_places_for_city
from backend.query_parse import extract_city
from backend.geo_match import (
    district_from_text,
    match_place,
    next_spread_district,
    sort_by_distance,
)
from backend.itinerary_patch import extract_json, normalize_time_slot
from backend.database.place_coords import fill_missing_coords
from dotenv import load_dotenv
from urllib.parse import quote_plus
from collections import Counter
import os
import random

def guess_time_slot(activity: str) -> str:
    """Guess logical time slot based on activity keywords."""
    act_lower = activity.lower()
    for slot, keywords in ACTIVITY_TIME_RULES.items():
        if any(word in act_lower for word in keywords):
            return slot
    return "afternoon"  # default fallback

def reorder_itinerary(activities):
    """Sort activities in logical day order (morning → afternoon → evening)."""
    grouped = {"morning": [], "afternoon": [], "evening": []}
    for act in activities:
        slot = guess_time_slot(act)
        grouped[slot].append(act)

    ordered = grouped["morning"] + grouped["afternoon"] + grouped["evening"]
    return ordered

def normalize_activity_times(itinerary):
    """Fill missing activity times only. Do not move an explicit Morning/Afternoon/Evening."""
    for day in itinerary.get("itinerary", []):
        for activity in day.get("activities", []):
            existing = normalize_time_slot(activity.get("time"))
            if existing:
                activity["time"] = existing
                continue
            act_text = (activity.get("activity") or "").lower()
            if any(word in act_text for word in ACTIVITY_TIME_RULES["evening"]):
                activity["time"] = "Evening"
            elif any(word in act_text for word in ACTIVITY_TIME_RULES["morning"]):
                activity["time"] = "Morning"
            elif any(word in act_text for word in ACTIVITY_TIME_RULES["afternoon"]):
                activity["time"] = "Afternoon"
            else:
                activity["time"] = "Afternoon"
    return itinerary

def format_itinerary(activities):
    """Format itinerary including food suggestions. Prefer structured time over keywords."""
    grouped = {"morning": [], "afternoon": [], "evening": []}
    for a in activities:
        slot = normalize_time_slot(a.get("time"))
        key = slot.lower() if slot else guess_time_slot(a.get("activity", ""))
        if key not in grouped:
            key = "afternoon"
        grouped[key].append(a)

    output = []
    for slot in ["morning", "afternoon", "evening"]:
        if grouped[slot]:
            output.append(f"\n☀️ {slot.capitalize()}:")
            for a in grouped[slot]:
                act = a.get("activity", "")
                food = a.get("food", "")
                if food:
                    output.append(f"- {act} 🍽️ Suggestion: {food}")
                else:
                    output.append(f"- {act}")
    return "\n".join(output)

ACTIVITY_TIME_RULES = {
    "morning": [
        "temple", "museum", "park", "hike", "breakfast", "brunch",
        "garden", "memorial", "scenic view"
    ],
    "afternoon": [
        "shopping", "district", "market(day)", "lunch", "art", "mall",
        "zoo", "aquarium", "tour", "street"
    ],
    "evening": [
        "night market", "Night Market","bar", "club", "street food", "dinner", "rooftop",
        "river", "night view", "show", "night"
    ]
}

SYSTEM_PROMPT = """
You are a travel itinerary generator.

You ALWAYS respond with **valid JSON only** — no markdown, no extra commentary, no prose.

Your goal:
Given a user query, YouTube travel transcript context, and a list of attractions/food/activities,
return a structured JSON itinerary.

Format:
{
  "itinerary": [
    {
      "day": 1,
      "activities": [
        {
          "time": "Morning",
          "activity": "Visit Longshan Temple in Wanhua District",
          "food": "Taiwanese breakfast at Fuhang Soy Milk",
          "source": "video_id1"
        },
        {
          "time": "Afternoon",
          "activity": "Explore Taipei 101 observation deck",
          "food": "Din Tai Fung at Taipei 101",
          "source": "video_id2"
        },
        {
          "time": "Evening",
          "activity": "Walk around Raohe Night Market",
          "food": "Try pepper buns and bubble tea",
          "source": "video_id3"
        }
      ]
    }
  ],
  "sources": ["video_id1", "video_id2", "video_id3"]
}

Rules:
- Return ONLY valid JSON.
- Each day must have 3 time slots: Morning, Afternoon, Evening.
- Each time slot must have an 'activity' AND a 'food' entry.
- 'food' should be specific (restaurant, market, or dish).
- Spread days across different districts; do not keep every slot in one neighborhood.
- If unknown, make a realistic guess.
- Do not use markdown or text explanations.
"""

load_dotenv()

KEY = os.getenv("GROQ_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

client = Groq(api_key=KEY)
load_index()


def _has_itinerary(parsed) -> bool:
    return isinstance(parsed, dict) and bool(parsed.get("itinerary"))


FOOD_OPTIONS_PER_SLOT = 3


def maps_url(place: dict) -> str:
    """Link to the venue on Google Maps. Plain URL, so it costs nothing."""
    query = quote_plus(place.get("name") or "")
    url = f"https://www.google.com/maps/search/?api=1&query={query}"
    place_id = place.get("place_id")
    if place_id:
        url += f"&query_place_id={quote_plus(place_id)}"
    return url


def food_option(place: dict) -> dict:
    """Fields the UI needs to show a card and drop a map pin."""
    place = fill_missing_coords(place)
    return {
        "name": place.get("name"),
        "district": place.get("district"),
        "rating": place.get("rating"),
        "address": place.get("address"),
        "lat": place.get("lat"),
        "lon": place.get("lon"),
        "place_id": place.get("place_id"),
        "maps_url": maps_url(place),
    }


PLACEHOLDER_FOOD = {"", "n/a", "na", "none", "tbd", "unknown", "-"}


def _missing_food(value) -> bool:
    return str(value or "").strip().lower() in PLACEHOLDER_FOOD


#how many of the nearest restaurants to sample from, so food stays close to the
#activity without every trip returning the single closest venue
NEARBY_SHORTLIST = 8


def ensure_food(
    itinerary: dict,
    structured_places: list,
    options_per_slot: int = FOOD_OPTIONS_PER_SLOT,
    anchor_places: list | None = None,
):
    """Fill any missing food slot and attach nearby restaurant options.

    `anchor_places` is the full place list for the city. When an activity's text
    matches one of those places we rank food by real distance; otherwise we fall
    back to matching the district name out of the activity text.
    """
    restaurants = [p for p in structured_places if p.get("category")=="restaurant"]
    districts = sorted({p.get("district", "") for p in structured_places if p.get("district")})
    anchors = anchor_places or []
    used_districts: Counter = Counter()

    def pick_restaurants_for_activity(act_text, already_used, anchor):
        nearby = []
        if anchor:
            nearby = sort_by_distance(
                restaurants, float(anchor["lat"]), float(anchor["lon"])
            )[:NEARBY_SHORTLIST]

        matched_district = district_from_text(act_text, districts)
        # No landmark and no named district: rotate so leftover slots are not
        # all filled from the Anping-heavy high-rating pile.
        if not matched_district and not anchor:
            matched_district = next_spread_district(districts, used_districts)

        near, elsewhere = [], []
        for r in restaurants:
            if matched_district and r.get("district") == matched_district:
                near.append(r)
            else:
                elsewhere.append(r)

        #best first: nearest to the activity, then same district, then anywhere.
        #repeats are only allowed once every fresh option is exhausted.
        tiers = (
            [r for r in nearby if r.get("name") not in already_used],
            [r for r in near if r.get("name") not in already_used],
            [r for r in elsewhere if r.get("name") not in already_used],
            near,
            elsewhere,
        )

        picks, taken = [], set()
        for tier in tiers:
            if len(picks) >= options_per_slot:
                break
            candidates = [r for r in tier if r.get("name") not in taken]
            if not candidates:
                continue
            for r in random.sample(
                candidates, min(options_per_slot - len(picks), len(candidates))
            ):
                picks.append(r)
                taken.add(r.get("name"))

        if anchor:
            picks = sort_by_distance(picks, float(anchor["lat"]), float(anchor["lon"]))
        return picks

    for day in itinerary.get("itinerary", []):
        used_today = {
            option.get("name")
            for activity in day.get("activities", [])
            for option in activity.get("food_options") or []
        }
        for activity in day.get("activities", []):
            act_text = activity.get("activity", "")
            anchor = match_place(act_text, anchors) if anchors else None
            if anchor and not activity.get("place"):
                activity["place"] = food_option(anchor) | {
                    "category": anchor.get("category")
                }

            has_food = not _missing_food(activity.get("food"))
            existing = [fill_missing_coords(option) for option in activity.get("food_options") or []]
            if existing:
                activity["food_options"] = existing
            existing_have_coords = any(
                option.get("lat") is not None and option.get("lon") is not None
                for option in existing
            )
            if has_food and existing and existing_have_coords:
                continue
            picks = pick_restaurants_for_activity(act_text, used_today, anchor)
            used_today.update(p.get("name") for p in picks)
            used_districts.update(p.get("district") for p in picks if p.get("district"))
            if not has_food:
                if picks:
                    top = picks[0]
                    activity["food"] = (
                        f"{top.get('name')} ({top.get('district','unknown district')})"
                    )
                else:
                    activity["food"] = "unknown"
            if not existing_have_coords:
                activity["food_options"] = [food_option(p) for p in picks]
    return itinerary


def generate_itinerary(query, k=10, max_retries=2):
    # 1) retrieval
    context = retrieve_context(query, k=k)
    context_text = "\n\n".join([f"From {c['file_name']}: {c['chunk']}" for c in context])

    # 2) structured places from SQL
    city_name = extract_city(query)
    structured_places = get_places_for_city(city_name) if city_name else []
    structured_text = "\n".join(f"{p['category'].capitalize()} - {p['name']} ({p['district']}, {p['rating']}⭐)" for p in structured_places)

    combined_context = f"Semantic travel insights:\n{context_text}\n\nLocal recommendations from Google Places:\n{structured_text}"

    user_prompt = f"Generate a structured travel itinerary for this query:\n{query}\n\nCONTEXT:\n{combined_context}"

    # Step 3: call LLM
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.6
    )
    raw_output = response.choices[0].message.content.strip()
    parsed = extract_json(raw_output)

    # Step 4: retry/fixer loop
    retries = 0
    while not _has_itinerary(parsed) and retries < max_retries:
        retries += 1
        # Strong fixer: insist on valid JSON only
        fix_prompt = (
            "The previous response was not valid JSON. "
            "Please REWRITE ONLY the data as VALID JSON following this exact schema (no markdown, no surrounding text, no backticks):\n\n"
            f"{SYSTEM_PROMPT}\n\n"
            f"Previous (invalid) response:\n{raw_output}\n\nReturn only the corrected JSON now."
        )
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": fix_prompt}
            ],
            temperature=0
        )
        raw_output = (response.choices[0].message.content or "").strip()
        parsed = extract_json(raw_output)

    if not _has_itinerary(parsed):
        return {"error": "No JSON Found", "raw": raw_output}

    # Normalize times, ensure food, then return
    itinerary = normalize_activity_times(parsed)
    itinerary = ensure_food(itinerary, structured_places)
    return itinerary