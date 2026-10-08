from backend.gc_utils import download_transcripts, list_transcripts
import faiss
import numpy as np
import pickle
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import os, json
import time
import spacy
from tqdm import tqdm
from groq import Groq, APITimeoutError, APIError

load_dotenv()

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
    global index, metadata, location_cache

    transcript_text = download_transcripts(bucket_name, file_name)
    if not transcript_text.strip():
        print(f"⚠️ Skipping {file_name}: empty transcript")
        return

    # --- Step 1: Chunk the transcript ---
    chunks = chunk_text(transcript_text)
    if not chunks:
        print(f"⚠️ Skipping {file_name}: no chunks created")
        return

    # --- Step 2: Embed and add to FAISS ---
    embeddings = np.array(embed_chunks(chunks))
    if embeddings.ndim == 1:
        embeddings = embeddings.reshape(1, -1)

    if index is None:
        dim = embeddings.shape[1]
        index = faiss.IndexFlatL2(dim)
        print(f"✅ Created new FAISS index with dimension {dim}")

    index.add(embeddings)
    print(f"📥 Added {len(chunks)} chunks from {file_name} to FAISS index")

    # --- Step 3: Extract locations efficiently ---
    print(f"🌍 Checking cache and extracting new locations for {file_name}...")

    all_entities = []
    uncached_chunks = []
    uncached_indices = []

    for i, chunk in enumerate(chunks):
        cache_key = f"{file_name}:{str(hash(chunk))}"
        if cache_key in location_cache:
            all_entities.append(location_cache[cache_key])
        else:
            uncached_chunks.append(chunk)
            uncached_indices.append(i)
            all_entities.append(None)  # placeholder

    # --- Step 4: Extract only for uncached chunks ---
    if uncached_chunks:
        print(f"🧠 Extracting {len(uncached_chunks)} uncached chunks using hybrid model...")
        new_entities = extract_locations_hybrid(uncached_chunks, location_cache, file_name)

        for i, entities in zip(uncached_indices, new_entities):
            cache_key = f"{file_name}:{str(hash(chunks[i]))}"
            location_cache[cache_key] = entities
            all_entities[i] = entities
    else:
        print("✅ All chunks found in cache — skipping extraction.")

    # --- Step 5: Save metadata ---
    for chunk, entities in zip(chunks, all_entities):
        metadata.append({
            "file_name": file_name,
            "chunk": chunk,
            "locations": entities or []
        })

    # --- Step 6: Save updated cache once ---
    with open("location_cache.json", "w") as f:
        json.dump(location_cache, f, indent=2)
    print(f"💾 Saved updated location cache with {len(location_cache)} entries.")
    save_index(index, metadata, "faiss_index.bin", "metadata.pkl")
    print(f"💾 Saved FAISS index after processing {file_name}\n")

def add_all_transcripts(bucket_name: str, prefix: str = ""):
    """Index ALL transcripts in the bucket (with optional prefix filter)."""
    global index, metadata, location_cache

    file_names = list_transcripts(bucket_name, prefix)

    # --- Load previous FAISS index & metadata if they exist ---
    if os.path.exists("faiss_index.bin") and os.path.exists("metadata.pkl"):
        try:
            index = faiss.read_index("faiss_index.bin")
            with open("metadata.pkl", "rb") as f:
                metadata = pickle.load(f)
            print(f"✅ Loaded FAISS index with {index.ntotal} vectors and {len(metadata)} metadata entries.")
        except Exception as e:
            print(f"⚠️ Could not load previous index: {e}")
            index = None
            metadata = []
    else:
        print("🆕 Starting with a new FAISS index and metadata list.")
        index = None
        metadata = []

    # --- Load previous cache if it exists ---
    if os.path.exists("location_cache.json"):
        with open("location_cache.json", "r") as f:
            location_cache = json.load(f)
        print(f"✅ Loaded location cache with {len(location_cache)} entries.")
    else:
        location_cache = {}
        print("🆕 Starting with an empty location cache.")

    # --- Skip already processed files ---
    processed_files = {m["file_name"] for m in metadata} if metadata else set()

    for file_name in file_names:
        if file_name in processed_files:
            print(f"⏩ Skipping {file_name} (already indexed).")
            continue

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
def retrieve_context(query, k= 10, require_locations=False):
    query_embeddings = model.encode([query]).astype("float32")
    distances, indices = index.search(query_embeddings, k)

    from backend.query_parse import extract_query_locations

    query_locs = [loc.lower() for loc in extract_query_locations(query)]

    retrieved_chunks = []
    for idx in indices[0]:
        if idx < 0:
            continue
        row = dict(metadata[idx])
        haystack = (row.get("chunk") or "").lower()
        tagged = [str(loc).lower() for loc in (row.get("locations") or [])]
        matches_query = bool(query_locs) and any(
            loc in haystack or loc in tagged for loc in query_locs
        )
        if require_locations and query_locs and not matches_query:
            continue
        row["match_priority"] = matches_query
        retrieved_chunks.append(row)

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

def get_locations_spacy(text:str):
    doc = nlp(text)
    locations = [ent.text for ent in doc.ents if ent.label_ in ("GPE", "LOC", "FAC")]
    return list(set(locations))

def extract_locations_hybrid(chunks, cache, file_name):
    results = []
    missing_chunks = []
    missing_indices = []

    total_chunks = len(chunks)
    print(f"\n🌍 Starting hybrid extraction for {file_name} ({total_chunks} chunks)\n")

    # Pass 1: Check cache + run spaCy
    for i, chunk in enumerate(tqdm(chunks, desc="🔎 Checking cache & spaCy", unit="chunk")):
        cache_key = f"{file_name}:{hash(chunk)}"

        # ✅ Cache hit
        if cache_key in cache:
            results.append(cache[cache_key])
            continue

        # 🔍 Try spaCy extraction
        spacy_locs = get_locations_spacy(chunk)
        if spacy_locs:
            tqdm.write(f"✅ spaCy found {len(spacy_locs)} locations in chunk {i}")
            results.append(spacy_locs)
            cache[cache_key] = spacy_locs
        else:
            tqdm.write(f"⚠️ spaCy found no locations in chunk {i} → queuing for Flan-T5")
            results.append(None)
            missing_chunks.append(chunk)
            missing_indices.append(i)

    
    if missing_chunks:
        use_flan = os.getenv("INDEX_USE_FLAN", "").strip().lower() in ("1", "true", "yes")
        if not use_flan:
            print(
                f"\nSkipping FLAN-T5 for {len(missing_chunks)} chunks (spaCy-only). "
                "Set INDEX_USE_FLAN=1 to enable. Retrieve still matches on chunk text.\n"
            )
            for idx in missing_indices:
                results[idx] = []
                cache_key = f"{file_name}:{hash(chunks[idx])}"
                cache[cache_key] = []
        else:
            print(f"\n🤖 Flan-T5 on {len(missing_chunks)} missing chunks...\n")

            start_time = time.perf_counter()
            from local_llm import extract_locations_flan_batch

            flan_results = extract_locations_flan_batch(missing_chunks, batch_size=2)
            elapsed_time = time.perf_counter() - start_time

            print(f"⏱️ Flan-T5 extraction completed in {elapsed_time:.2f} seconds\n")

            for idx, locs in zip(missing_indices, flan_results):
                results[idx] = locs
                cache_key = f"{file_name}:{hash(chunks[idx])}"
                cache[cache_key] = locs

    print(f"✅ Completed hybrid extraction for {file_name}\n")
    return results