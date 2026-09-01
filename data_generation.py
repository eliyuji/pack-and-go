import argparse
from backend.youtube_service import (
    search_youtube,
    gen_transcript,
    get_video_metadata,
    save_transcript_and_metadata
)
from backend.db import get_connection
import backend.env  # noqa: F401


# --- DB check helper ---
def transcript_exists(video_id: str) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM youtube_transcripts WHERE video_id = %s LIMIT 1;", (video_id,))
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return exists
    except Exception as e:
        print(f"⚠️ Error checking DB for {video_id}: {e}")
        return False


def process_locations(locations: list[str], max_results: int = 5):
    all_video_ids = []

    query_templates = [
        "{} travel",
        "{} vlog",
        "{} walking tour",
        "{} food tour",
        "{} things to do",
        "{} travel guide",
    ]

    for location in locations:
        print(f"\nSearching videos for: {location}")

        queries = [template.format(location) for template in query_templates]

        for query in queries:
            print(f"   Running query: {query}")
            try:
                videos = search_youtube(query, max_results=max_results)
            except Exception as e:
                print(f" Error searching YouTube for {query}: {e}")
                continue

            for v in videos:
                video_id = v.get("videoId")
                if not video_id:
                    continue
                url = f"https://www.youtube.com/watch?v={video_id}"

                if transcript_exists(video_id):
                    print(f"Skipping {video_id} (already processed)")
                    continue

                all_video_ids.append(video_id)
                print(f"Processing: {v['title']} ({video_id})")

                try:
                    transcript = gen_transcript(url, video_id)
                    if not transcript:
                        print(f"No transcript for {video_id}, skipping.")
                        continue

                    metadata = get_video_metadata(video_id)
                    if not metadata:
                        print(f"No metadata for {video_id}, skipping.")
                        continue

                    title = metadata["title"]
                    tags = metadata.get("tags", [])

                    save_transcript_and_metadata(
                        video_id=video_id,
                        title=title,
                        url=url,
                        tags=tags,
                        transcript=transcript,
                    )
                    print(f"Saved transcript + metadata for {title}")

                except Exception as e:
                    print(f"Error processing video {video_id}: {e}")
                    continue

    return all_video_ids

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Search YouTube travel videos, transcribe them, and store text in GCS + metadata in Postgres."
    )
    parser.add_argument(
        "locations",
        nargs="+",
        help='City or region names, e.g. "Taipei" "Hong Kong"',
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Videos per search query (default 5). Each location runs 6 query templates.",
    )
    args = parser.parse_args()

    video_ids = process_locations(args.locations, max_results=args.max_results)
    print("\nProcessing complete!")
    print("All collected video IDs:", video_ids)