from fastapi import FastAPI, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from backend.youtube_service import search_youtube
from backend.youtube_service import gen_transcript
from backend.youtube_service import get_video_metadata
from backend.youtube_service import save_transcript_and_metadata
from rag_pipeline import generate_itinerary,format_itinerary,reorder_itinerary,guess_time_slot

app = FastAPI()

# Allow frontend (Next.js) to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryReq(BaseModel):
    query: str

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

#Testing endpoint: http://127.0.0.1:8000/youtube?q=funny+cats
@app.get("/youtube")
def youtube_search(q:str):
    return{"results": search_youtube(q)}

#Testing Transcript Endpoint: http://127.0.0.1:8000/transcript/dQw4w9WgXcQ
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
class QueryReq(BaseModel):
    query:str
@app.post("/itinerary")
def get_itinerary(request: QueryReq):
    result = generate_itinerary(request.query)

    # if generation failed
    if "error" in result:
        return result

    # result["itinerary"] should be a list of days
    formatted_days = []
    for day in result.get("itinerary", []):
        day_num = day.get("day", "?")
        activities = [a["activity"] for a in day.get("activities", [])]
        formatted = format_itinerary(activities)
        formatted_days.append(f"\n🗓️ Day {day_num}\n{formatted}")

    formatted_text = "\n".join(formatted_days)
    return {"itinerary": formatted_text, "sources": result.get("sources", [])}