from google.cloud import storage

def read_transcripts(bucket_name: str, file_name:str) -> str:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    return blob.download_as_text()