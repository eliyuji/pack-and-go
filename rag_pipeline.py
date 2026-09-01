from groq import Groq
import json
from semantic_search import load_index, retrieve_context
from backend.database.attraction_query import get_places_for_city
from dotenv import load_dotenv
import os
import random
import re

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
    """
    Corrects mislabeled activity times (e.g., night markets under 'Afternoon').
    """
    for day in itinerary.get("itinerary", []):
        for activity in day["activities"]:
            act_text = activity["activity"].lower()

            # Detect obvious night-time attractions
            if any(word in act_text for word in ACTIVITY_TIME_RULES["evening"]):
                activity["time"] = "Evening"
            elif any(word in act_text for word in ACTIVITY_TIME_RULES["morning"]):
                activity["time"] = "Morning"
            elif any(word in act_text for word in ACTIVITY_TIME_RULES["afternoon"]):
                activity["time"] = "Afternoon"
            else:
                # Default fallback if uncertain
                activity["time"] = "Afternoon"
    return itinerary

def format_itinerary(activities):
    """Format itinerary including food suggestions."""
    grouped = {"morning": [], "afternoon": [], "evening": []}
    for a in activities:
        slot = guess_time_slot(a["activity"])
        grouped[slot].append(a)

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
- If unknown, make a realistic guess.
- Do not use markdown or text explanations.
"""

load_dotenv()

KEY = os.getenv("GROQ_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

client = Groq(api_key=KEY)
load_index()

def extract_json(text: str):
    """
    Tries multiple strategies to extract valid JSON from a model response.
    Handles:
    - ```json ... ``` fenced blocks
    - Plain JSON without code fences
    - Text with JSON embedded inside
    """
    # Try matching fenced JSON
    match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
    if match:
        candidate = match.group(1)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Try matching any {...} block that looks like JSON
    match = re.search(r"(\{[\s\S]*\})", text)
    if match:
        candidate = match.group(1)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Try direct load if the whole text is just JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
def ensure_food(itinerary:dict, structured_places:list):
    """If any time slot is missing food, it'll fill it with t """
    restaurants = [p for p in structured_places if p.get("category")=="restaurant"]
    districts = sorted({p.get("district", "") for p in structured_places if p.get("district")})
    #if we can match the district from the activity suggested
    def pick_restaurant_for_activity(act_text):
        act_low = (act_text or "").lower()
        matched_district = None
        for d in districts:
              if d and d.lower().split()[0] in act_low:
                  matched_district = d
        candid = [r for r in restaurants if r.get("district") == matched_district] if matched_district else restaurants
        if not candid:
            #if no district found then fall back to any district (should later on search for places within x radius)
            candid = restaurants
        if not candid:
            return "unknown"
        sel = random.choice(candid)
        return f"{sel.get('name')} ({sel.get('district','unknown district')})"
    
    for day in itinerary.get("itinerary", []):
        for activity in day.get("activities", []):
            if not activity.get("food"):
                activity_text = activity.get("activity", "")
                activity["food"] = pick_restaurant_for_activity(activity_text)
    return itinerary

def extract_json(text: str):
    # fenced ```json blocks
    match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
    if match:
        cand = match.group(1)
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            pass
    # any top-level {...}
    match = re.search(r"(\{[\s\S]*\})", text)
    if match:
        cand = match.group(1)
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            pass
    # whole text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None

def generate_itinerary(query, k=10, max_retries=2):
    # 1) retrieval
    context = retrieve_context(query, k=k)
    context_text = "\n\n".join([f"From {c['file_name']}: {c['chunk']}" for c in context])

    # 2) structured places from SQL
    city_name = (query.split(" in ")[-1].strip().title() if " in " in query else None)
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
    while not parsed and retries < max_retries:
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
        raw_output = response.choices[0].message.content.strip()
        parsed = extract_json(raw_output)

    if not parsed:
        return {"error": "No JSON Found", "raw": raw_output}

    # Normalize times, ensure food, then return
    itinerary = normalize_activity_times(parsed)
    itinerary = ensure_food(itinerary, structured_places)
    return itinerary