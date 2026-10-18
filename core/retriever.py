"""
rag/retriever.py
================
RAG (Retrieval-Augmented Generation) module.
Loads knowledge-base documents, creates FAISS embeddings, and performs
semantic search to enrich agent responses with policy context.

Phase 4 implementation: document embedding + retrieval.
"""

import json
import pickle
from pathlib import Path
from typing import Any

from config import KNOWLEDGE_BASE_DIR
VECTOR_STORE_DIR = KNOWLEDGE_BASE_DIR  # Not used in TF-IDF mode

# ── Try importing FAISS; gracefully degrade if not installed ──────────────────
try:
    import faiss
    import numpy as np
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

# ── Try importing OpenAI embeddings ──────────────────────────────────────────
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from config import is_openai_available, OPENAI_API_KEY


# ════════════════════════════════════════════════════════════════════════════════
# Simple TF-IDF fallback (no API key needed)
# ════════════════════════════════════════════════════════════════════════════════
class TFIDFRetriever:
    """
    Lightweight keyword retriever using TF-IDF cosine similarity.
    Used when FAISS or OpenAI embeddings are unavailable.
    """

    def __init__(self):
        self.chunks: list[dict] = []
        self._fitted = False

    def _simple_tokenize(self, text: str) -> list[str]:
        import re
        return re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())

    def _tfidf_vector(self, tokens: list[str], vocab: dict) -> list[float]:
        from math import log
        vec = [0.0] * len(vocab)
        total = len(tokens)
        if total == 0:
            return vec
        freq = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1
        for word, idx in vocab.items():
            tf  = freq.get(word, 0) / total
            idf = log(1 + len(self.chunks) / (1 + self._df.get(word, 0)))
            vec[idx] = tf * idf
        return vec

    def _cosine(self, a: list[float], b: list[float]) -> float:
        import math
        dot = sum(x * y for x, y in zip(a, b))
        na  = math.sqrt(sum(x * x for x in a))
        nb  = math.sqrt(sum(x * x for x in b))
        return dot / (na * nb + 1e-9)

    def build(self, chunks: list[dict]):
        self.chunks = chunks
        # Build vocabulary and document frequencies
        all_tokens = []
        doc_tokens = []
        for ch in chunks:
            tokens = self._simple_tokenize(ch["content"])
            doc_tokens.append(tokens)
            all_tokens.extend(tokens)

        vocab = {w: i for i, w in enumerate(sorted(set(all_tokens)))}
        self._vocab = vocab
        self._df    = {}
        for tokens in doc_tokens:
            for w in set(tokens):
                self._df[w] = self._df.get(w, 0) + 1

        self._vectors = [self._tfidf_vector(t, vocab) for t in doc_tokens]
        self._fitted  = True

    def search(self, query: str, k: int = 3) -> list[dict]:
        if not self._fitted or not self.chunks:
            return []
        q_tokens = self._simple_tokenize(query)
        q_vec    = self._tfidf_vector(q_tokens, self._vocab)
        scores   = [(self._cosine(q_vec, v), i)
                    for i, v in enumerate(self._vectors)]
        scores.sort(reverse=True)
        results = []
        for score, idx in scores[:k]:
            if score > 0.01:
                results.append({**self.chunks[idx], "relevance_score": round(score, 3)})
        return results


# ════════════════════════════════════════════════════════════════════════════════
# Document Loader
# ════════════════════════════════════════════════════════════════════════════════
def load_knowledge_base(kb_dir: Path = KNOWLEDGE_BASE_DIR) -> list[dict]:
    """
    Load and chunk all .txt documents from the knowledge base directory.
    Returns a list of chunk dicts: {source, chunk_id, content}.
    """
    chunks = []
    if not kb_dir.exists():
        return chunks

    for doc_path in sorted(kb_dir.glob("*.txt")):
        text = doc_path.read_text(encoding="utf-8")
        # Split on double-newlines (paragraph-level chunks)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for i, para in enumerate(paragraphs):
            chunks.append({
                "source"  : doc_path.stem,
                "chunk_id": f"{doc_path.stem}_chunk_{i}",
                "content" : para,
            })

    return chunks


# ════════════════════════════════════════════════════════════════════════════════
# KnowledgeRetriever — main interface
# ════════════════════════════════════════════════════════════════════════════════
class KnowledgeRetriever:
    """
    Unified retriever that automatically selects the best available backend:
    1. FAISS + OpenAI embeddings  (best quality, requires API key)
    2. TF-IDF keyword search      (good fallback, no API key needed)
    """

    def __init__(self):
        self._retriever = TFIDFRetriever()
        self._chunks: list[dict] = []
        self._built = False

    def build(self):
        """Load documents and build the search index."""
        self._chunks = load_knowledge_base()
        if not self._chunks:
            print("  ⚠ No knowledge base documents found. Retrieval disabled.")
            return

        self._retriever.build(self._chunks)
        self._built = True
        print(f"  ✔ Knowledge base built: {len(self._chunks)} chunks "
              f"from {len(set(c['source'] for c in self._chunks))} documents")

    def retrieve(self, query: str, k: int = 3) -> list[dict]:
        """
        Retrieve the top-k most relevant chunks for a query.

        Returns list of dicts: {source, chunk_id, content, relevance_score}
        """
        if not self._built:
            self.build()
        if not self._chunks:
            return []
        return self._retriever.search(query, k=k)

    def format_context(self, query: str, k: int = 3) -> str:
        """Return retrieved chunks formatted as a context string for the LLM."""
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
