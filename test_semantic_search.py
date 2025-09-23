from semantic_search import add_all_transcripts, search, save_index_files

BUCKET_NAME = "pag-transcripts"

from semantic_search import load_index_files, search

if __name__ == "__main__":
    load_index_files()  # load saved FAISS index + metadata

    results = search("Food in Hong Kong", k=5)

    print("Search results:")
    for r in results:
        print(f"[{r['file_name']}] {r['chunk']} (distance={r['distance']:.4f})")


