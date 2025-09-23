from google.cloud import storage

def download_transcripts(bucket_name: str, file_name:str) -> str:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    return blob.download_as_text()

def list_transcripts(bucket_name: str, prefix: str = "") -> list[str]:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix=prefix)
    return[blob.name for blob in blobs if blob.name.endswith(".txt")]