"""
retrieval/embedder.py
======================
TF-IDF based embedding and similarity search.
Lightweight keyword retriever — no API key needed.
"""

import math
import re


class TFIDFRetriever:
    """
    Lightweight keyword retriever using TF-IDF cosine similarity.
    Used when FAISS or OpenAI embeddings are unavailable.
    """

    def __init__(self):
        self.chunks: list[dict] = []
        self._fitted = False

    def _simple_tokenize(self, text: str) -> list[str]:
        return re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())

    def _tfidf_vector(self, tokens: list[str], vocab: dict) -> list[float]:
        vec = [0.0] * len(vocab)
        total = len(tokens)
        if total == 0:
            return vec
        freq = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1
        for word, idx in vocab.items():
            tf  = freq.get(word, 0) / total
            idf = math.log(1 + len(self.chunks) / (1 + self._df.get(word, 0)))
            vec[idx] = tf * idf
        return vec

    def _cosine(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na  = math.sqrt(sum(x * x for x in a))
        nb  = math.sqrt(sum(x * x for x in b))
        return dot / (na * nb + 1e-9)

    def build(self, chunks: list[dict]):
        self.chunks = chunks
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
