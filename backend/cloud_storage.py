from google.cloud import storage

def upload_transcript(file_name: str, content: str, bucket_name: str) -> str:
    """
    Uploads a string as a file to a Google Cloud Storage bucket.

    Args:
        file_name: Name of the file in the bucket (e.g., "video123.txt").
        content: The text content to upload.
        bucket_name: Your GCS bucket name.

    Returns:
        The GCS URI of the uploaded file.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    blob.upload_from_string(content)
    return f"gs://{bucket_name}/{file_name}"
