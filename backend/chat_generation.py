from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
import json
from semantic_search import retrieve_context
from backend.database.attraction_query import get_places_for_city
from backend.query_parse import extract_city
from backend.itinerary_patch import (
    extract_json,
    modification_summary,
    normalize_time_slot,
    patch_activity,
    patch_day,
)
import os
from dotenv import load_dotenv

load_dotenv()

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

llm = ChatGroq(
    api_key=os.getenv("GROQ_KEY"),
    model=GROQ_MODEL,
    temperature=0.6
)


class ItineraryState(TypedDict):
    original_query: str
    feedback: str
    itinerary: Dict[str, Any]
    messages: List[Any]
    semantic_context: str
    structured_places: List[Dict]
    modification_intent: Dict[str, Any]
    final_itinerary: Dict[str, Any]
    error: str


def retrieve_travel_context(state: ItineraryState) -> ItineraryState:
    query = state["original_query"]

    context = retrieve_context(query, k=10)
    context_text = "\n\n".join([f"From {c['file_name']}: {c['chunk']}" for c in context])

    city_name = extract_city(query)
    structured_places = get_places_for_city(city_name) if city_name else []

    state["semantic_context"] = context_text
    state["structured_places"] = structured_places
    return state


def understand_modification_intent(state: ItineraryState) -> ItineraryState:
    feedback = state.get("feedback", "")
    current_itinerary = state.get("itinerary", {})

    if not feedback:
        state["modification_intent"] = {"type": "generate_new"}
        return state

    intent_prompt = f"""
You are analyzing user feedback about a travel itinerary.

Current Itinerary:
{json.dumps(current_itinerary, indent=2)}

User Feedback: "{feedback}"

Analyze the feedback and return a JSON object with:
- "type": "modify_day" | "modify_activity" | "add_preference" | "regenerate_all"
- "target_day": day number if modifying specific day (int or null)
- "target_time": "Morning" | "Afternoon" | "Evening" if modifying specific time slot (or null)
- "action": "replace" | "add" | "remove" | "adjust"
- "preference": what the user wants (string)

Examples:
- "Change Day 2 morning activity" -> {{"type": "modify_activity", "target_day": 2, "target_time": "Morning", "action": "replace", "preference": "user wants different morning activity"}}
- "Add more food experiences" -> {{"type": "add_preference", "preference": "more food experiences"}}
- "Remove shopping from Day 3" -> {{"type": "modify_day", "target_day": 3, "action": "remove", "preference": "no shopping"}}

Return ONLY valid JSON, no markdown.
"""

    response = llm.invoke([SystemMessage(content=intent_prompt)])
    intent = extract_json(response.content)
    if not isinstance(intent, dict) or not intent.get("type"):
        # Keep the current trip; treat unclear feedback as a preference tweak.
        intent = {"type": "add_preference", "preference": feedback}
    if intent.get("target_time"):
        intent["target_time"] = normalize_time_slot(intent["target_time"])
    state["modification_intent"] = intent
    return state


def generate_or_modify_itinerary(state: ItineraryState) -> ItineraryState:
    intent = state.get("modification_intent") or {}
    current_itinerary = state.get("itinerary") or {}
    intent_type = intent.get("type")

    try:
        if intent_type == "generate_new":
            itinerary = generate_full_itinerary(state)
        elif intent_type == "modify_activity":
            if not intent.get("target_day") or not intent.get("target_time"):
                raise ValueError("Could not tell which day and time slot to change.")
            itinerary = modify_specific_activity(state, current_itinerary, intent)
        elif intent_type == "modify_day":
            if not intent.get("target_day"):
                raise ValueError("Could not tell which day to change.")
            itinerary = modify_entire_day(state, current_itinerary, intent)
        elif intent_type in ("add_preference", "regenerate_all"):
            itinerary = regenerate_with_preferences(state, current_itinerary, intent)
            if not itinerary or not itinerary.get("itinerary"):
                raise ValueError("Could not apply that preference. The current itinerary was left unchanged.")
        else:
            raise ValueError("Could not understand that change request.")

        if not itinerary or not itinerary.get("itinerary"):
            raise ValueError("Failed to produce a valid itinerary.")

        state["itinerary"] = itinerary
        state["final_itinerary"] = itinerary
        state["error"] = ""
    except ValueError as exc:
        state["error"] = str(exc)
        state["final_itinerary"] = current_itinerary
    return state


def generate_full_itinerary(state: ItineraryState) -> Dict[str, Any]:
    query = state["original_query"]
    context_text = state["semantic_context"]
    structured_places = state["structured_places"]

    structured_text = "\n".join(
        f"{p['category'].capitalize()} - {p['name']} ({p['district']}, {p['rating']}⭐)"
        for p in structured_places
    )

    system_prompt = """
You are a travel itinerary generator. Return ONLY valid JSON with this structure:
{
  "itinerary": [
    {
      "day": 1,
      "activities": [
        {"time": "Morning", "activity": "...", "food": "..."},
        {"time": "Afternoon", "activity": "...", "food": "..."},
        {"time": "Evening", "activity": "...", "food": "..."}
      ]
    }
  ]
}
No markdown, no extra text.
"""

    user_prompt = f"""
Generate a travel itinerary for: {query}

Travel Context:
{context_text}

Local Places:
{structured_text}
"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    parsed = {}
    raw = ""
    for attempt in range(3):
        response = llm.invoke(messages)
        raw = response.content if isinstance(response.content, str) else str(response.content or "")
        parsed = extract_json(raw)
        if isinstance(parsed, dict) and parsed.get("itinerary"):
            return parsed
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=(
                    "The previous response was not valid itinerary JSON. "
                    "Rewrite ONLY valid JSON with an 'itinerary' array. No markdown.\n\n"
                    f"Previous response:\n{raw[:4000]}"
                )
            ),
        ]
    return parsed if isinstance(parsed, dict) else {}


def modify_specific_activity(state: ItineraryState, current: Dict, intent: Dict) -> Dict[str, Any]:
    """Ask the LLM for one replacement slot, then patch it in Python."""
    target_day = intent["target_day"]
    target_time = intent.get("target_time")
    preference = intent.get("preference", "")
    context_text = state["semantic_context"]

    system_prompt = """
You are replacing ONE activity in a travel itinerary.
Return ONLY valid JSON for the replacement slot:
{"time": "Morning", "activity": "...", "food": "..."}
No markdown, no other days, no extra text.
"""

    user_prompt = f"""
Current itinerary:
{json.dumps(current, indent=2)}

Replace Day {target_day} {target_time} with something that matches: {preference}

Travel context:
{context_text[:1000]}
"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ])
    new_activity = extract_json(response.content)
    if not isinstance(new_activity, dict) or not new_activity.get("activity"):
        raise ValueError("Could not generate a replacement activity.")
    return patch_activity(current, target_day, target_time, new_activity)


def modify_entire_day(state: ItineraryState, current: Dict, intent: Dict) -> Dict[str, Any]:
    """Ask the LLM for one replacement day, then patch it in Python."""
    target_day = intent["target_day"]
    preference = intent.get("preference", "")
    context_text = state["semantic_context"]

    system_prompt = """
You are replacing ONE day in a travel itinerary.
Return ONLY valid JSON for that day:
{
  "day": 2,
  "activities": [
    {"time": "Morning", "activity": "...", "food": "..."},
    {"time": "Afternoon", "activity": "...", "food": "..."},
    {"time": "Evening", "activity": "...", "food": "..."}
  ]
}
No markdown, no other days, no extra text.
"""

    user_prompt = f"""
Current itinerary:
{json.dumps(current, indent=2)}

Regenerate Day {target_day} with these preferences: {preference}

Travel context:
{context_text[:1000]}
"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ])
    new_day = extract_json(response.content)
    if not new_day:
        raise ValueError(f"Could not generate a replacement for Day {target_day}.")
    return patch_day(current, target_day, new_day)


def regenerate_with_preferences(state: ItineraryState, current: Dict, intent: Dict) -> Dict[str, Any]:
    preference = intent.get("preference", "")

    system_prompt = """
You are updating a travel itinerary based on user preferences.
Return the complete updated itinerary as JSON with the same number of days.
Each day must have Morning, Afternoon, and Evening activities with food.
"""

    user_prompt = f"""
Current Itinerary:
{json.dumps(current, indent=2)}

User Preferences:
{preference}

Context:
{state["semantic_context"][:1000]}

Update the itinerary to match these preferences while keeping the same structure and trip length.
"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ])
    parsed = extract_json(response.content)
    if isinstance(parsed, dict) and parsed.get("itinerary"):
        return parsed
    return current


def create_itinerary_graph():
    workflow = StateGraph(ItineraryState)
    workflow.add_node("retrieve_context", retrieve_travel_context)
    workflow.add_node("understand_intent", understand_modification_intent)
    workflow.add_node("generate_modify", generate_or_modify_itinerary)
    workflow.set_entry_point("retrieve_context")
    workflow.add_edge("retrieve_context", "understand_intent")
    workflow.add_edge("understand_intent", "generate_modify")
    workflow.add_edge("generate_modify", END)
    return workflow.compile()


itinerary_graph = create_itinerary_graph()


def process_itinerary_request(
    query: str,
    feedback: str = "",
    current_itinerary: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Run the LangGraph workflow.

    Returns:
        {
          "structured": <itinerary dict>,
          "modification": {"type", "target_day", "target_time"},
          "error": optional str
        }
    """
    initial_state = {
        "original_query": query,
        "feedback": feedback,
        "itinerary": current_itinerary or {},
        "messages": [],
        "semantic_context": "",
        "structured_places": [],
        "modification_intent": {},
        "final_itinerary": {},
        "error": "",
    }

    result = itinerary_graph.invoke(initial_state)
    payload = {
        "structured": result.get("final_itinerary") or current_itinerary or {},
        "modification": modification_summary(result.get("modification_intent") or {}),
    }
    if result.get("error"):
        payload["error"] = result["error"]
    return payload
