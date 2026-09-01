import os
import backend.env  # noqa: F401
from semantic_search import add_all_transcripts, save_index_files

BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

if __name__ == "__main__":
    if not BUCKET_NAME:
        raise ValueError("GCS_BUCKET_NAME is not set in .env")
    add_all_transcripts(BUCKET_NAME)
    save_index_files()
