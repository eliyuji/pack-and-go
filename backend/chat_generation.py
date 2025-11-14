from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import json
from semantic_search import retrieve_context
from backend.database.attraction_query import get_places_for_city
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize LLM
llm = ChatGroq(
    api_key=os.getenv("GROQ_KEY"),
    model="llama-3.1-8b-instant",
    temperature=0.6
)

# Define the state schema
class ItineraryState(TypedDict):
    """State that gets passed through the graph"""
    # User inputs
    original_query: str
    feedback: str
    
    # Current itinerary
    itinerary: Dict[str, Any]  # The full structured itinerary
    
    # Conversation context
    messages: List[Any]
    
    # Retrieved context
    semantic_context: str
    structured_places: List[Dict]
    
    # Intent understanding
    modification_intent: Dict[str, Any]  # What the user wants to change
    
    # Output
    final_itinerary: Dict[str, Any]


def retrieve_travel_context(state: ItineraryState) -> ItineraryState:
    """Node 1: Retrieve semantic and structured context"""
    query = state["original_query"]
    
    # Semantic search
    context = retrieve_context(query, k=10)
    context_text = "\n\n".join([f"From {c['file_name']}: {c['chunk']}" for c in context])
    
    # Structured places from database
    city_name = (query.split(" in ")[-1].strip().title() if " in " in query else None)
    structured_places = get_places_for_city(city_name) if city_name else []
    
    state["semantic_context"] = context_text
    state["structured_places"] = structured_places
    
    return state


def understand_modification_intent(state: ItineraryState) -> ItineraryState:
    """Node 2: Understand what the user wants to modify"""
    feedback = state.get("feedback", "")
    current_itinerary = state.get("itinerary", {})
    
    if not feedback:
        # No feedback means initial generation
        state["modification_intent"] = {"type": "generate_new"}
        return state
    
    # Use LLM to understand the intent
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
    
    try:
        # Extract JSON from response
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        intent = json.loads(content)
        state["modification_intent"] = intent
    except:
        # Fallback: treat as general regeneration
        state["modification_intent"] = {
            "type": "add_preference",
            "preference": feedback
        }
    
    return state


def generate_or_modify_itinerary(state: ItineraryState) -> ItineraryState:
    """Node 3: Generate new itinerary or modify existing one"""
    intent = state["modification_intent"]
    current_itinerary = state.get("itinerary", {})
    
    if intent["type"] == "generate_new":
        # Initial generation
        itinerary = generate_full_itinerary(state)
        state["itinerary"] = itinerary
        state["final_itinerary"] = itinerary
    
    elif intent["type"] == "modify_activity" and intent.get("target_day"):
        # Targeted modification
        itinerary = modify_specific_activity(state, current_itinerary, intent)
        state["itinerary"] = itinerary
        state["final_itinerary"] = itinerary
    
    elif intent["type"] == "modify_day" and intent.get("target_day"):
        # Modify entire day
        itinerary = modify_entire_day(state, current_itinerary, intent)
        state["itinerary"] = itinerary
        state["final_itinerary"] = itinerary
    
    else:
        # General preference adjustment - regenerate with preferences
        itinerary = regenerate_with_preferences(state, current_itinerary, intent)
        state["itinerary"] = itinerary
        state["final_itinerary"] = itinerary
    
    return state


def generate_full_itinerary(state: ItineraryState) -> Dict[str, Any]:
    """Generate a brand new itinerary"""
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
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ])
    
    return extract_json(response.content)


def modify_specific_activity(state: ItineraryState, current: Dict, intent: Dict) -> Dict[str, Any]:
    """Modify a specific activity in a specific time slot"""
    target_day = intent["target_day"]
    target_time = intent.get("target_time")
    preference = intent.get("preference", "")
    
    context_text = state["semantic_context"]
    structured_places = state["structured_places"]
    
    system_prompt = """
You are modifying a specific activity in a travel itinerary.
Return the COMPLETE updated itinerary as JSON (same structure as input).
Only change the specified activity, keep everything else the same.
"""
    
    user_prompt = f"""
Current Itinerary:
{json.dumps(current, indent=2)}

Modification Request:
- Day: {target_day}
- Time: {target_time}
- User wants: {preference}

Available context:
{context_text[:1000]}

Return the FULL updated itinerary in the same JSON format.
"""
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ])
    
    return extract_json(response.content) or current


def modify_entire_day(state: ItineraryState, current: Dict, intent: Dict) -> Dict[str, Any]:
    """Regenerate an entire day"""
    target_day = intent["target_day"]
    preference = intent.get("preference", "")
    
    system_prompt = """
You are regenerating one day of a travel itinerary.
Return the COMPLETE itinerary with the updated day.
Keep all other days exactly the same.
"""
    
    user_prompt = f"""
Current Itinerary:
{json.dumps(current, indent=2)}

Regenerate Day {target_day} with these preferences:
{preference}

Return the FULL updated itinerary.
"""
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ])
    
    return extract_json(response.content) or current


def regenerate_with_preferences(state: ItineraryState, current: Dict, intent: Dict) -> Dict[str, Any]:
    """Regenerate entire itinerary with new preferences"""
    preference = intent.get("preference", "")
    
    system_prompt = """
You are updating a travel itinerary based on user preferences.
Return the complete updated itinerary as JSON.
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
    
    return extract_json(response.content) or current


def extract_json(text: str) -> Dict[str, Any]:
    """Extract JSON from LLM response"""
    import re
    
    # Try fenced blocks
    match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
    
    # Try any {...}
    match = re.search(r"(\{[\s\S]*\})", text)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
    
    # Try direct parse
    try:
        return json.loads(text)
    except:
        return {}


# Build the LangGraph
def create_itinerary_graph():
    """Create the stateful LangGraph workflow"""
    workflow = StateGraph(ItineraryState)
    
    # Add nodes
    workflow.add_node("retrieve_context", retrieve_travel_context)
    workflow.add_node("understand_intent", understand_modification_intent)
    workflow.add_node("generate_modify", generate_or_modify_itinerary)
    
    # Define edges
    workflow.set_entry_point("retrieve_context")
    workflow.add_edge("retrieve_context", "understand_intent")
    workflow.add_edge("understand_intent", "generate_modify")
    workflow.add_edge("generate_modify", END)
    
    return workflow.compile()


# Create the graph instance
itinerary_graph = create_itinerary_graph()


# API endpoint function
def process_itinerary_request(query: str, feedback: str = "", current_itinerary: Dict = None):
    """
    Main function to call from FastAPI endpoint
    
    Args:
        query: Original travel query
        feedback: User feedback for modifications (empty for initial generation)
        current_itinerary: Existing itinerary to modify (None for initial generation)
    
    Returns:
        Dict with updated itinerary
    """
    initial_state = {
        "original_query": query,
        "feedback": feedback,
        "itinerary": current_itinerary or {},
        "messages": [],
        "semantic_context": "",
        "structured_places": [],
        "modification_intent": {},
        "final_itinerary": {}
    }
    
    # Run the graph
    result = itinerary_graph.invoke(initial_state)
    
    return result["final_itinerary"]