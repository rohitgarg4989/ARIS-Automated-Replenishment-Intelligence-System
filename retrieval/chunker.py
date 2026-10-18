"""
retrieval/chunker.py
=====================
Splits documents into chunks for indexing.
"""


def chunk_text(text: str, source: str) -> list[dict]:
    """
    Split text into paragraph-level chunks.
    Returns a list of chunk dicts: {source, chunk_id, content}.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    for i, para in enumerate(paragraphs):
        chunks.append({
            "source"  : source,
            "chunk_id": f"{source}_chunk_{i}",
            "content" : para,
        })
    return chunks
