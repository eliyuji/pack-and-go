import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# Load local embedding model
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# Step 1: Chunk text
def chunk_text(text, max_words=30):
    words = text.split()
    return [" ".join(words[i:i+max_words]) for i in range(0, len(words), max_words)]

# Step 2: Embed chunks
def embed_chunks(chunks):
    embeddings = model.encode(chunks)
    return np.array(embeddings).astype("float32")

# Step 3: Create FAISS index
def create_faiss_index(embeddings):
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    return index

# Step 4: Search function
def semantic_search(query, index, chunks, top_k=2):
    query_embedding = model.encode([query]).astype("float32")
    distances, indices = index.search(query_embedding, top_k)
    return [chunks[i] for i in indices[0]]

# === Test ===
if __name__ == "__main__":
    text = """Artificial intelligence is transforming industries.
              Machine learning helps computers learn from data.
              Neural networks are inspired by the human brain.
              OpenAI develops powerful models for natural language processing.
              FAISS is a library for efficient similarity search."""
    
    chunks = chunk_text(text, max_words=10)
    print("Chunks:", chunks)

    embeddings = embed_chunks(chunks)
    index = create_faiss_index(embeddings)

    query = "Tell me about neural networks"
    results = semantic_search(query, index, chunks, top_k=2)

    print("\nSearch results:")
    for res in results:
        print("-", res)
