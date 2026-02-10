"""
Build Vector Index for RAG
==========================
Run this after seeding rag_packages to build TF-IDF vectors
for semantic search / RAG retrieval.

Usage:
  python build_vectors.py

Requires: PostgreSQL running with rag_packages seeded.
"""

import sys
import os
import time

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/rail_planner"
)


def main():
    print("=" * 60)
    print("  Railbookers RAG Vector Index Builder")
    print("=" * 60)

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Check packages exist
        count = db.execute(text("SELECT COUNT(*) FROM rag_packages")).scalar()
        print(f"\nPackages in database: {count}")

        if count == 0:
            print("ERROR: No packages found. Run seed_rag_packages.py first.")
            return

        # Import and build vector store
        from app.services.vector_store import VectorStore

        store = VectorStore(db)
        print("\nBuilding TF-IDF vectors...")
        start = time.time()

        indexed = store.build_index()

        elapsed = time.time() - start
        print(f"\nVector index built successfully!")
        print(f"  Packages indexed: {indexed}")
        print(f"  Time: {elapsed:.1f}s")

        # Verify
        vec_count = db.execute(text("SELECT COUNT(*) FROM package_vectors")).scalar()
        print(f"  Vectors in DB: {vec_count}")

        # Quick test search
        print("\nRunning test search: 'scenic train journey through alps switzerland'")
        results = store.semantic_search("scenic train journey through alps switzerland", top_k=5)
        if results:
            print(f"  Found {len(results)} results:")
            for pkg_id, score in results[:5]:
                row = db.execute(
                    text("SELECT external_name FROM rag_packages WHERE id = :id"),
                    {"id": pkg_id}
                ).fetchone()
                name = row[0] if row else "Unknown"
                print(f"    [{score:.3f}] {name}")
        else:
            print("  No results (this is unusual, check vectorizer)")

        print("\nDone! RAG vector store is ready.")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
