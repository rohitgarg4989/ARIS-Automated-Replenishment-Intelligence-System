"""
scripts/build_faiss_index.py
=============================
Build a FAISS index from knowledge base documents.

Usage: python scripts/build_faiss_index.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from retrieval.document_loader import load_knowledge_base
from retrieval.chunker import chunk_text
from retrieval.faiss_store import FAISSStore
from deployment.config import FAISS_INDEX_DIR


def main():
    print("\n🔨 Building FAISS index...\n")

    docs = load_knowledge_base()
    if not docs:
        print("⚠ No documents found in knowledge/raw/. Nothing to index.")
        return

    chunks = []
    for doc in docs:
        chunks.extend(chunk_text(doc["content"], doc["source"]))

    print(f"  Loaded {len(docs)} documents → {len(chunks)} chunks")

    store = FAISSStore()
    if not store.is_available:
        print("⚠ FAISS or OpenAI not available. Install faiss-cpu and set OPENAI_API_KEY.")
        return

    store.build(chunks)
    store.save(FAISS_INDEX_DIR)
    print(f"  ✔ FAISS index saved to {FAISS_INDEX_DIR}")
    print(f"\n✅ Index built successfully.\n")


if __name__ == "__main__":
    main()
