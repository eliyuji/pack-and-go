from backend.db import Base, engine
from models import YouTubeTranscript

print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Done ✅")
