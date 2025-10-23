from groq import Groq
import json
from semantic_search import load_index, retrieve_context
from dotenv import load_dotenv
import os
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
    """Format the itinerary with time-of-day headers."""
    ordered = reorder_itinerary(activities)
    grouped = {"morning": [], "afternoon": [], "evening": []}
    for act in ordered:
        grouped[guess_time_slot(act)].append(act)
    
    output = []
    for slot in ["morning", "afternoon", "evening"]:
        if grouped[slot]:
            output.append(f"\n☀️ {slot.capitalize()}:")
            output.extend(f"- {a}" for a in grouped[slot])
    return "\n".join(output)

ACTIVITY_TIME_RULES = {
    "morning": [
        "temple", "museum", "park", "hike", "breakfast", "brunch",
        "garden", "memorial", "scenic view"
    ],
    "afternoon": [
        "shopping", "district", "market (day)", "lunch", "art", "mall",
        "zoo", "aquarium", "tour", "street"
    ],
    "evening": [
        "night market", "bar", "club", "street food", "dinner", "rooftop",
        "river", "night view", "show"
    ]
}

SYSTEM_PROMPT = """
You are a helpful travel assistant.
Given a user query and transcript context from YouTube travel videos,
create a structured travel itinerary in JSON format.

Format:
{
  "itinerary": [
    {
      "day": 1,
      "activities": [
        {"time": "Morning", "activity": "Visit Longshan Temple in Wanhua District", "source": "video_id"},
        {"time": "Afternoon", "activity": "Eat beef noodle soup at Yongkang Street", "source": "video_id"},
        {"time": "Evening", "activity": "Explore Raohe Night Market", "source": "video_id"}
      ]
    },
    {"day": 2, "activities": [...]}
  ],
  "sources": ["video_id1", "video_id2", ...]
}

Rules:
- Always respond in valid JSON.
- Be as specific as possible: include place names, neighborhoods, restaurants, landmarks, or exact attractions.
- Use the transcript context to extract specific locations.
- Each day MUST include three time slots: Morning, Afternoon, and Evening — even if evening activity must be inferred.
- If the transcript context is vague, make an informed guess but label source as "unknown".
"""

load_dotenv()

KEY = os.getenv("GROQ_KEY")

client = Groq(api_key=KEY)
load_index()

def build_prompt(query, context_chunks):
    context_text = "\n\n".join(
        [f"From {c['file_name']}: {c['chunk']}" for c in context_chunks]
    )

    return f"{SYSTEM_PROMPT}\n\nUSER QUERY: {query}\n\nCONTEXT (use specific place names when available):\n{context_text}"
def generate_itinerary(query, k=10):
    context = retrieve_context(query, k=k)
    full_prompt = build_prompt(query, context)

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": full_prompt}
        ],
        temperature=0.7
    )

    raw_output = response.choices[0].message.content.strip()

    # 🧹 Step 1: Extract JSON between ```json ... ``` if present
    json_match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", raw_output)
    if json_match:
        json_text = json_match.group(1)
    else:
        # Fallback: try to find the first JSON-like block
        json_match = re.search(r"(\{[\s\S]*\})", raw_output)
        json_text = json_match.group(1) if json_match else None

    # 🧠 Step 2: Parse JSON safely
    if json_text:
        try:
            itinerary = json.loads(json_text)
            itinerary = normalize_activity_times(itinerary)
            return itinerary
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON decode error: {e}")
            return {"error": "Invalid JSON after cleanup", "raw": raw_output}

    # ❌ Step 3: If no JSON found at all
    return {"error": "No JSON found in model output", "raw": raw_output}