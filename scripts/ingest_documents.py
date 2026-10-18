"""
scripts/ingest_documents.py
=============================
Ingest raw documents into the knowledge base and generate sample data.

Usage: python scripts/ingest_documents.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.generate_data import (
    generate_sales_data,
    generate_inventory_data,
    generate_supplier_data,
    generate_supplier_feedback,
    create_knowledge_base,
)


def main():
    print("\n📦 Ingesting documents and generating sample data...\n")

    generate_sales_data()
    generate_inventory_data()
    generate_supplier_data()
    generate_supplier_feedback()
    create_knowledge_base()

    print("\n✅ All data generated and documents ingested.\n")


if __name__ == "__main__":
    main()
