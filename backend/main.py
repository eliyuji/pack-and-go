from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from fastapi.middleware.cors import CORSMiddleware
from backend.youtube_service import search_youtube
from backend.youtube_service import gen_transcript
from backend.youtube_service import get_video_metadata
from backend.youtube_service import save_transcript_and_metadata
from rag_pipeline import generate_itinerary, format_itinerary, reorder_itinerary, guess_time_slot
from rag_pipeline import normalize_activity_times, ensure_food

# Import LangGraph functions
try:
    from backend.chat_generation import process_itinerary_request
    LANGGRAPH_ENABLED = True
except ImportError:
    LANGGRAPH_ENABLED = False
    print("Warning: LangGraph not available. Install with: pip install langgraph langchain-groq")

app = FastAPI()

# Allow frontend (Next.js + Streamlit) to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js frontend
        "http://localhost:8501",  # Streamlit default port
        "*"  # Allow all for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryReq(BaseModel):
    query: str

class FeedbackRequest(BaseModel):
    query: str  # Original query
    feedback: str  # User feedback
    current_itinerary: Dict[str, Any]  # Current structured itinerary

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI!"}

@app.get("/health")
def health_check():
    langgraph_status = "enabled" if LANGGRAPH_ENABLED else "disabled"
    return {
        "status": "ok",
        "langgraph": langgraph_status
    }

# Testing endpoint: http://127.0.0.1:8000/youtube?q=funny+cats
@app.get("/youtube")
def youtube_search(q: str):
    return {"results": search_youtube(q)}

# Testing Transcript Endpoint: http://127.0.0.1:8000/transcript/dQw4w9WgXcQ
@app.get("/transcript/{video_id}")
def transcript(video_id: str):
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    text = gen_transcript(youtube_url, video_id)
    
    metadata = get_video_metadata(video_id)
    if not metadata:
        return {"error": "Video not found"}
    
    gcs_uri = save_transcript_and_metadata(
        video_id,
        metadata["title"],
        youtube_url,
        metadata["tags"],
        text
    )
    
    return {
        "videoId": video_id,
        "title": metadata["title"],
        "tags": metadata["tags"],
        "transcript_gcs": gcs_uri
    }

# ORIGINAL ITINERARY ENDPOINT (kept for backward compatibility)
@app.post("/itinerary")
def get_itinerary(request: QueryReq):
    """
    Original itinerary endpoint - generates fresh itinerary each time.
    Use /itinerary/v2 for LangGraph-powered conversational refinements.
    """
    result = generate_itinerary(request.query)

    # if generation failed
    if "error" in result:
        return result

    # result["itinerary"] should be a list of days
    formatted_days = []
    for day in result.get("itinerary", []):
        day_num = day.get("day", "?")
        activities = day.get("activities", [])
        formatted = format_itinerary(activities)
        formatted_days.append(f"\n🗓️ Day {day_num}\n{formatted}")

    formatted_text = "\n".join(formatted_days)
    return {
        "itinerary": formatted_text,
        "structured": result,  # Add structured data for frontend
        "sources": result.get("sources", [])
    }


# NEW LANGGRAPH-POWERED ENDPOINTS
@app.post("/itinerary/v2")
def generate_initial_itinerary_v2(request: QueryReq):
    """
    NEW: Generate initial itinerary using LangGraph.
    This endpoint supports conversational refinements via /itinerary/refine
    """
    if not LANGGRAPH_ENABLED:
        # Fallback to original method
        return get_itinerary(request)
    
    try:
        # Use LangGraph to generate
        result = process_itinerary_request(
            query=request.query,
            feedback="",
            current_itinerary=None
        )
        
        if not result or "error" in result:
            raise HTTPException(status_code=500, detail="Failed to generate itinerary")
        
        # Post-process (normalize times, ensure food)
        result = normalize_activity_times(result)
        # Note: You may want to pass structured_places to ensure_food
        result = ensure_food(result, [])
        
        # Format for frontend display
        formatted_days = []
        for day in result.get("itinerary", []):
            day_num = day.get("day", "?")
            activities = day.get("activities", [])
            formatted = format_itinerary(activities)
            formatted_days.append(f"\n🗓️ Day {day_num}\n{formatted}")
        
        formatted_text = "\n".join(formatted_days)
        
        return {
            "itinerary": formatted_text,
            "structured": result,  # Keep structured version for modifications
            "sources": result.get("sources", []),
            "version": "v2-langgraph"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/itinerary/refine")
def refine_itinerary(request: FeedbackRequest):
    """
    NEW: Refine existing itinerary based on user feedback.
    Uses LangGraph to make targeted modifications instead of full regeneration.
    
    Example feedback:
    - "Change Day 2 morning activity to something more cultural"
    - "Add more food experiences throughout"
    - "Remove shopping from Day 3"
    - "Make the trip more budget-friendly"
    """
    if not LANGGRAPH_ENABLED:
        # Fallback: regenerate with combined query
        combined_query = f"{request.query}. {request.feedback}"
        return get_itinerary(QueryReq(query=combined_query))
    
    try:
        # Use LangGraph to intelligently modify
        result = process_itinerary_request(
            query=request.query,
            feedback=request.feedback,
            current_itinerary=request.current_itinerary
        )
        
        if not result or "error" in result:
            raise HTTPException(status_code=500, detail="Failed to refine itinerary")
        
        # Post-process
        result = normalize_activity_times(result)
        result = ensure_food(result, [])
        
        # Format for frontend display
        formatted_days = []
        for day in result.get("itinerary", []):
            day_num = day.get("day", "?")
            activities = day.get("activities", [])
            formatted = format_itinerary(activities)
            formatted_days.append(f"\n🗓️ Day {day_num}\n{formatted}")
        
        formatted_text = "\n".join(formatted_days)
        
        return {
            "itinerary": formatted_text,
            "structured": result,  # Keep structured version for future modifications
            "sources": result.get("sources", []),
            "version": "v2-langgraph",
            "modification_applied": True
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# UTILITY ENDPOINT: Check modification intent without generating
@app.post("/itinerary/analyze-feedback")
def analyze_feedback(request: FeedbackRequest):
    """
    Utility endpoint: Analyze user feedback to understand modification intent.
    Useful for showing users what changes will be made before applying them.
    """
    if not LANGGRAPH_ENABLED:
        return {"message": "LangGraph not enabled", "intent": "regenerate_all"}
    
    try:
        from backend.chat_generation import understand_modification_intent
        
        state = {
            "feedback": request.feedback,
            "itinerary": request.current_itinerary,
            "modification_intent": {}
        }
        
        result_state = understand_modification_intent(state)
        intent = result_state.get("modification_intent", {})
        
        # Create human-readable description
        intent_type = intent.get("type", "unknown")
        descriptions = {
            "modify_activity": f"Will modify specific activity on Day {intent.get('target_day')} {intent.get('target_time', '')}",
            "modify_day": f"Will regenerate entire Day {intent.get('target_day')}",
            "add_preference": f"Will adjust itinerary with preference: {intent.get('preference', '')}",
            "regenerate_all": "Will regenerate entire itinerary"
        }
        
        return {
            "intent": intent,
            "description": descriptions.get(intent_type, "Unknown modification")
        }
    
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)