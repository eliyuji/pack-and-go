import faiss
import numpy as np

class VectorStore:
    def __init__(self, dim: int):
        self.index = faiss.IndexFlatL2(dim)
        self.chunks = []  # store the actual text chunks

    def add(self, embeddings: list[list[float]], texts: list[str]):
        self.index.add(np.array(embeddings).astype("float32"))
        self.chunks.extend(texts)

    def search(self, query_embedding: list[float], top_k: int = 5):
        D, I = self.index.search(np.array([query_embedding]).astype("float32"), top_k)
        return [self.chunks[i] for i in I[0]]
