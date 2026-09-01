from backend.db import Base, get_engine
from models import YouTubeTranscript  # noqa: F401

print("Creating tables...")
Base.metadata.create_all(bind=get_engine())
print("Done")
