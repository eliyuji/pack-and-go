from backend.embeddings import get_embedding
from backend.vector_store import VectorStore

def retrieve(query: str, store: VectorStore, top_k: int = 5):
    query_embedding = get_embedding(query)
    results = store.search(query_embedding, top_k=top_k)
    return results

