"""
retrieval/document_loader.py
=============================
Loads documents from the knowledge base directory.
"""

from pathlib import Path
from deployment.config import KNOWLEDGE_RAW_DIR


def load_knowledge_base(kb_dir: Path = KNOWLEDGE_RAW_DIR) -> list[dict]:
    """
    Load all .txt and .pdf documents from the knowledge base directory.
    Returns a list of dicts: {source, content}.
    """
    docs = []
    if not kb_dir.exists():
        return docs

    for doc_path in sorted(kb_dir.glob("*.txt")):
        text = doc_path.read_text(encoding="utf-8")
        docs.append({
            "source" : doc_path.stem,
            "content": text,
        })

    return docs
