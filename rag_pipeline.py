from openai import OpenAI
import json
from semantic_search import retrieve_context

SYSTEM_PROMPT = """
You are a helpful travel assistant.
Given a user query and transcript context from YouTube travel videos,
create a structured travel itinerary in JSON format.

Format:
{
  "itinerary": [
    {"day": 1, "activities": [ {"time": "Morning", "activity": "...", "source": "video_id"}, ... ]},
    {"day": 2, "activities": [...]}
  ],
  "sources": ["video_id1", "video_id2", ...]
}

Rules:
- Always respond in valid JSON.
- Reference video IDs from the provided context.
- If context is missing, make a best guess but mark source as "unknown".
"""

client = OpenAI()

def build_prompt(query, context_chunks):
    context_text = "\n\n".join(
        [f"From {c['file_name']}: {c['chunk']}" for c in context_chunks]
    )
    return f"{SYSTEM_PROMPT}\n\nUSER QUERY: {query}\n\nCONTEXT:\n{context_text}"

def generate_itinerary(query, k=5):
    context = retrieve_context(query, k=k)
    full_prompt = build_prompt(query, context)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": full_prompt}
        ],
        temperature=0.7
    )

    try:
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {"error": "Invalid JSON", "raw": response.choices[0].message.content}