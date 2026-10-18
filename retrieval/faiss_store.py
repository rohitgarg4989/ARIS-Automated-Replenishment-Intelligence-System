"""
retrieval/faiss_store.py
=========================
FAISS vector store for semantic search.
Falls back gracefully if FAISS is not installed.
"""

from pathlib import Path
from deployment.config import FAISS_INDEX_DIR

try:
    import faiss
    import numpy as np
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from deployment.config import is_openai_available, OPENAI_API_KEY


class FAISSStore:
    """
    FAISS-based vector store for semantic search.
    Requires faiss-cpu and OpenAI embeddings.
    """

    def __init__(self):
        self._index = None
        self._chunks: list[dict] = []
        self._ready = False

    @property
    def is_available(self) -> bool:
        return FAISS_AVAILABLE and is_openai_available()

    def build(self, chunks: list[dict]):
        """Build FAISS index from chunks using OpenAI embeddings."""
        if not self.is_available:
            return

        self._chunks = chunks
        client = OpenAI(api_key=OPENAI_API_KEY)

        texts = [c["content"] for c in chunks]
        response = client.embeddings.create(input=texts, model="text-embedding-3-small")
        embeddings = np.array([e.embedding for e in response.data], dtype="float32")

        dim = embeddings.shape[1]
        self._index = faiss.IndexFlatIP(dim)
        faiss.normalize_L2(embeddings)
        self._index.add(embeddings)
        self._ready = True

    def search(self, query: str, k: int = 3) -> list[dict]:
        if not self._ready:
            return []

        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.embeddings.create(input=[query], model="text-embedding-3-small")
        q_vec = np.array([response.data[0].embedding], dtype="float32")
        faiss.normalize_L2(q_vec)

        scores, indices = self._index.search(q_vec, k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self._chunks):
                results.append({
                    **self._chunks[idx],
                    "relevance_score": round(float(score), 3)
                })
        return results

    def save(self, path: Path = FAISS_INDEX_DIR):
        """Save FAISS index to disk."""
        if not self._ready or not FAISS_AVAILABLE:
            return
        import pickle
        path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(path / "index.faiss"))
        with open(path / "index.pkl", "wb") as f:
            pickle.dump(self._chunks, f)

    def load(self, path: Path = FAISS_INDEX_DIR) -> bool:
        """Load FAISS index from disk."""
        if not FAISS_AVAILABLE:
            return False
        import pickle
        index_file = path / "index.faiss"
        pkl_file   = path / "index.pkl"
        if not index_file.exists() or not pkl_file.exists():
            return False
        self._index = faiss.read_index(str(index_file))
        with open(pkl_file, "rb") as f:
            self._chunks = pickle.load(f)
        self._ready = True
        return True
