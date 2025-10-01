from semantic_search import add_all_transcripts, save_index_files

BUCKET_NAME = "pag-transcripts"

if __name__ == "__main__":
    add_all_transcripts(BUCKET_NAME)   # index ALL transcripts
    save_index_files()                 # save index + metadata to disk
