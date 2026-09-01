from google.cloud import storage


def upload_transcript(file_name: str, content: str, bucket_name: str) -> str:
    """
    Uploads a string as a file to a Google Cloud Storage bucket.

    Returns:
        The GCS URI of the uploaded file.
    """
    if not bucket_name:
        raise ValueError("GCS_BUCKET_NAME is not set.")
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    blob.upload_from_string(content)
    return f"gs://{bucket_name}/{file_name}"
