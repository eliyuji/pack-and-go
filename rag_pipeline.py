from groq import Groq
import json
from semantic_search import load_index, retrieve_context
from dotenv import load_dotenv
import os

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

    try:
        return json.loads(response.choices[0].message.content)
    except Exception:
        itinerary = {
            "error": "Invalid JSON",
            "raw": response.choices[0].message.content
        }

    return itinerary