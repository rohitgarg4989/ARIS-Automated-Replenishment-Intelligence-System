"""
retrieval/retriever.py
=======================
Unified retriever that automatically selects the best available backend:
1. FAISS + OpenAI embeddings  (best quality, requires API key)
2. TF-IDF keyword search      (good fallback, no API key needed)
"""

from pathlib import Path
from retrieval.document_loader import load_knowledge_base
from retrieval.chunker import chunk_text
from retrieval.embedder import TFIDFRetriever
from retrieval.faiss_store import FAISSStore


class KnowledgeRetriever:
    """
    Unified retriever with automatic backend selection.
    """

    def __init__(self):
        self._tfidf     = TFIDFRetriever()
        self._faiss     = FAISSStore()
        self._chunks: list[dict] = []
        self._built = False

    def build(self):
        """Load documents and build the search index."""
        docs = load_knowledge_base()
        if not docs:
            print("  ⚠ No knowledge base documents found. Retrieval disabled.")
            return

        self._chunks = []
        for doc in docs:
            self._chunks.extend(chunk_text(doc["content"], doc["source"]))

        if not self._chunks:
            return

        # Try FAISS first, fall back to TF-IDF
        if self._faiss.is_available:
            try:
                self._faiss.build(self._chunks)
                self._built = True
                print(f"  ✔ Knowledge base built (FAISS): {len(self._chunks)} chunks "
                      f"from {len(docs)} documents")
                return
            except Exception as e:
                print(f"  ⚠ FAISS build failed ({e}), falling back to TF-IDF.")

        self._tfidf.build(self._chunks)
        self._built = True
        print(f"  ✔ Knowledge base built (TF-IDF): {len(self._chunks)} chunks "
              f"from {len(docs)} documents")

    def retrieve(self, query: str, k: int = 3) -> list[dict]:
        if not self._built:
            self.build()
        if not self._chunks:
            return []
        if self._faiss._ready:
            return self._faiss.search(query, k=k)
        return self._tfidf.search(query, k=k)

    def format_context(self, query: str, k: int = 3) -> str:
        results = self.retrieve(query, k=k)
        if not results:
            return ""
        lines = ["[POLICY CONTEXT — from knowledge base]"]
        for r in results:
            lines.append(f"\n[{r['source']}]\n{r['content']}")
        return "\n".join(lines)

    @property
    def is_ready(self) -> bool:
        return self._built and bool(self._chunks)
