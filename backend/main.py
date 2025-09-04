from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from youtube_service import search_youtube
from youtube_service import gen_transcript

app = FastAPI()

# Allow frontend (Next.js) to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/youtube")
def youtube_search(q:str):
    return{"results": search_youtube(q)}

@app.get("/transcript/{video_id}")
def transcript(video_id: str):
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    text = gen_transcript(youtube_url, video_id)
    return {"video_id": video_id, "transcript": text}
