from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, func, ARRAY
from backend.db import Base

class YouTubeTranscript(Base):
    __tablename__ = "youtube_transcripts"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    tags = Column(ARRAY(String))  
    transcript = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
