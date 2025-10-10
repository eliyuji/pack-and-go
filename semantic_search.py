from backend.gc_utils import download_transcripts, list_transcripts
import faiss
import numpy as np
import pickle
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import os, json
import time
import spacy
from groq import Groq, APITimeoutError, APIError

load_dotenv()

KEY = os.getenv("GROQ_KEY")

client = Groq(api_key=KEY)

# Load local embedding model
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# Natural language processing english model, small ver for cpu opt.
nlp = spacy.load("en_core_web_sm")

CACHE_FILE = "location_cache.json"
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        location_cache = json.load(f)
else:
    location_cache = {}

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
        if chunk in location_cache:
            entities = location_cache[chunk]
            print("Already processed")
        else:

            entities = get_locations(chunk)
            #if not entities:
                # entities = get_locations_llm(chunk)
            location_cache[chunk] = entities
            save_cache()
            print("Finished Processing")
        if entities:
            print("Locations found ")
        else:
            print("No locations found")

        metadata.append({"file_name": file_name, "chunk": chunk, "locations": entities})

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
    """Load FAISS index and metadata from disk into globals."""
    global index, metadata
    index = faiss.read_index(index_path)
    with open(meta_path, "rb") as f:
        metadata = pickle.load(f)
    print(f"✅ Loaded FAISS index with {index.ntotal} vectors and {len(metadata)} metadata entries")

#RAG pipeline feeding
def retrieve_context(query, k= 5, require_locations=False):
    query_embeddings = model.encode([query]).astype("float32")
    distances, indices = index.search(query_embeddings, k)

    # Extract location(s) from the query
    query_locs = get_locations(query)

    retrieved_chunks = []
    for idx in indices[0]:
        chunk = metadata[idx]

        # Optional: prioritize chunks matching query location
        if query_locs and any(loc in chunk.get("locations", []) for loc in query_locs):
            chunk["match_priority"] = True
        else:
            chunk["match_priority"] = False

        retrieved_chunks.append(chunk)

    # Sort to show matching locations first
    retrieved_chunks.sort(key=lambda c: c["match_priority"], reverse=True)
    return retrieved_chunks

# Wrapper functions
def save_index_files():
    save_index(index, metadata)

def load_index_files():
    global index, metadata
    index, metadata = load_index()

# Method for extracting named locations metadata

def save_cache():
    with open(CACHE_FILE, "w") as f:
        json.dump(location_cache, f, indent=2)

def get_locations(text:str):
    doc = nlp(text)
    locations = [ent.text for ent in doc.ents if ent.label_ in ("GPE", "LOC", "FAC")]
    return list(set(locations))

def get_locations_llm(text: str, retries=3, delay=3):
    if text in location_cache:
        return location_cache[text]
     
    prompt = f"""
    Extract all specific locations, landmarks, restaurants, or neighborhoods mentioned
    in the following text. Return a JSON array of strings, no explanations.

    Text: {text}
    """
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                timeout=20  
            )

            import json
            result = json.loads(response.choices[0].message.content)
            location_cache[text] = result
            save_cache()
            return result
        
        #retry with delay to relieve llm request calls
        except (APITimeoutError, APIError, json.JSONDecodeError) as e:
            print(f"⚠️ Retry {attempt+1}/{retries} after error: {e}")
            time.sleep(delay)
    print("❌ Failed to extract locations after retries.")
    location_cache[text] = []
    save_cache()
    return []


