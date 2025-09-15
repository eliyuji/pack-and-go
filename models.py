from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import func
from backend.db import Base

class YouTubeTranscript(Base):
    __tablename__ = "youtube_transcripts"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String, unique=True, index=True)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    tags = Column(ARRAY(String), default=[])  # <- PostgreSQL array
    transcript = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
