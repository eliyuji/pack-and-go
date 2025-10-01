from backend.gc_utils import download_transcripts, list_transcripts
import faiss
import numpy as np
import pickle
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

# Load local embedding model
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

index = None
metadata = []

def chunk_text(text, max_words=50):
    words = text.split()
    return [" ".join(words[i:i+max_words]) for i in range(0, len(words), max_words)]

def embed_chunks(chunks):
    embeddings = model.encode(chunks)
    embeddings = np.array(embeddings).astype("float32")
    if embeddings.ndim == 1:  # if only 1 embedding error with 1D vector
        embeddings = embeddings.reshape(1, -1)
    return embeddings


def add_transcript_to_index(bucket_name: str, file_name: str):
    global index, metadata

    transcript_text = download_transcripts(bucket_name, file_name)
    if not transcript_text.strip():
        print(f"⚠️ Skipping {file_name}: empty transcript")
        return

    chunks = chunk_text(transcript_text)
    if not chunks:
        print(f"⚠️ Skipping {file_name}: no chunks created")
        return

    embeddings = embed_chunks(chunks)
    embeddings = np.array(embeddings)

    if embeddings.size == 0:
        print(f"⚠️ Skipping {file_name}: empty embeddings")
        return

    if embeddings.ndim == 1:
        embeddings = embeddings.reshape(1, -1)

    if index is None:
        dim = embeddings.shape[1]
        index = faiss.IndexFlatL2(dim)
    else:
        if embeddings.shape[1] != index.d:
            raise ValueError(
                #empty transcripts
                f"Embedding dimension mismatch for {file_name}: "
                f"expected {index.d}, got {embeddings.shape[1]}"
            )

    index.add(embeddings)

    for chunk in chunks:
        metadata.append({"file_name": file_name, "chunk": chunk})



def add_all_transcripts(bucket_name: str, prefix: str = ""):
    """Index ALL transcripts in the bucket (with optional prefix filter)."""
    file_names = list_transcripts(bucket_name, prefix)
    for file_name in file_names:
        print(f"Indexing: {file_name}")
        add_transcript_to_index(bucket_name, file_name)
#testing function
def search(query: str, k: int = 3):
    """Convert user query to embedding and search FAISS index."""
    global index, metadata
    # Step 1: Turn query into an embedding (using same model as transcripts)
    query_embedding = model.encode([query]).astype("float32")

    # Step 2: Search FAISS
    distances, indices = index.search(query_embedding, k)

    # Step 3: Return top chunks with distances
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        results.append({
            "file_name": metadata[idx]["file_name"],
            "chunk": metadata[idx]["chunk"],
            "distance": float(dist)
        })
    return results

# Helper functions for persisting Faiss
def save_index(index, metadata, index_path="faiss_index.bin", meta_path="metadata.pkl"):
    faiss.write_index(index, index_path)
    with open(meta_path, "wb") as f:
        pickle.dump(metadata, f)

def load_index(index_path="faiss_index.bin", meta_path="metadata.pkl"):
    """Load FAISS index and metadata from disk."""
    index = faiss.read_index(index_path)
    with open(meta_path, "rb") as f:
        metadata = pickle.load(f)
    return index, metadata

#RAG pipeline feeding
def retrieve_context(query, k= 5):
    query_embeddings = model.encode([query]).astype("float32")
    distances, indices = index.search(query_embeddings,k)

    retrieved_chunks = []
    for idx in indices[0]:
        retrieved_chunks.append(metadata[idx])

    return retrieved_chunks

# Wrapper functions
def save_index_files():
    save_index(index, metadata)

def load_index_files():
    global index, metadata
    index, metadata = load_index()
