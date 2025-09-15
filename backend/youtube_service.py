from googleapiclient.discovery import build
from backend.cloud_storage import upload_transcript
from youtube_transcript_api import YouTubeTranscriptApi
from backend.db import SessionLocal
from models import YouTubeTranscript
from dotenv import load_dotenv
import os
import whisper
from yt_dlp import YoutubeDL

load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")
BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

#API Setup
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

def search_youtube(query, max_results=5):
    
    #Service Client
    youtube = build(YOUTUBE_API_SERVICE_NAME,YOUTUBE_API_VERSION, developerKey=API_KEY)
    
    #Search Request
    request = youtube.search().list(
        q=query, part="snippet", type="video",maxResults=max_results
    )

    response = request.execute()

    results = []
    for item in response.get("items", []):#no item error handling
        results.append({
            "title": item["snippet"]["title"],
            "videoId": item["id"]["videoId"],
            "thumbnail": item["snippet"]["thumbnails"]["default"]["url"]
        })                       
    return results

def get_captions_transcript(vid_id:str ) -> str|None:
    """
    Try to fetch captions from Youtube. Return full transcription if available, else NONE
    """
    try:
        transcript = YouTubeTranscriptApi.get_transcript(vid_id)
        return " ".join([t["text"] for t in transcript])
    except Exception:
        return None
    
def whisper_get_transcript(video_url: str) -> str:
    """
    Downloads the audio from a YouTube video using yt-dlp,
    transcribes it with Whisper, and returns the text.
    """
    # Define a temporary audio file
    temp_audio_file = "temp_audio.mp4"

    # yt-dlp options
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': temp_audio_file,
        'quiet': True,  # suppress logs
        'no_warnings': True,
    }

    # Download audio
    with YoutubeDL(ydl_opts) as ydl:
        print(f"Downloading audio from: {video_url}")
        ydl.download([video_url])

    # Load Whisper model
    model = whisper.load_model("base")  # try "tiny" if slow
    print("Transcribing audio with Whisper...")
    result = model.transcribe(temp_audio_file)

    # Clean up
    os.remove(temp_audio_file)

    return result["text"]

def gen_transcript(vid_url:str, vid_id:str) -> str:
    transcript = get_captions_transcript(vid_id)
    if transcript:
        return transcript
    else:
        return whisper_get_transcript(vid_url)

def get_video_metadata(video_id: str):
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
    
    request = youtube.videos().list(
        part="snippet",
        id=video_id
    )
    
    response = request.execute()
    
    if not response["items"]:
        return None

    item = response["items"][0]["snippet"]
    title = item["title"]
    tags = item.get("tags", [])  # tags may not always exist
    return {"title": title, "tags": tags}
    
def save_transcript_and_metadata(video_id: str, title: str, url: str, tags: list[str], transcript: str):
    """
    Upload transcript to GCS and save metadata to Postgres.
    """
    # Upload to GCS
    file_name = f"{video_id}.txt"
    gcs_uri = upload_transcript(file_name, transcript, BUCKET_NAME)

    # Save metadata in Postgres
    session = SessionLocal()
    try:
        record = YouTubeTranscript(
            video_id=video_id,
            title=title,
            url=url,
            tags=tags,
            transcript=gcs_uri  # store the GCS path instead of full text
        )
        session.add(record)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
    return gcs_uri