"""
TF-IDF Vector Store for RAG (Retrieval Augmented Generation).
Builds and stores TF-IDF vectors for every package in the database.
At query time, vectorizes user preferences and finds semantically
similar packages using cosine similarity.

This is a proper RAG retrieval layer:
  Build phase  : package text -> TF-IDF sparse vector -> stored in DB
  Query phase  : user context -> TF-IDF vector -> cosine sim vs. all -> top N IDs
  Ranking phase: structured scoring on top N candidates

No external ML libraries needed. Pure Python + SQLite/PostgreSQL.
"""

from __future__ import annotations
import math
import re
import json
import logging
import time
from collections import Counter
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Text processing
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "is", "on", "at",
    "by", "with", "from", "as", "it", "its", "be", "are", "was", "were", "been",
    "has", "have", "had", "do", "does", "did", "will", "would", "could", "should",
    "this", "that", "these", "those", "such", "your", "our", "you", "we", "they",
    "their", "them", "he", "she", "his", "her", "all", "each", "every", "any",
    "not", "no", "but", "if", "than", "then", "also", "just", "only", "very",
    "more", "most", "so", "up", "out", "into", "over", "after", "before",
    "through", "during", "about", "between", "under", "again", "where", "when",
    "how", "what", "which", "who", "whom", "why", "can", "may", "must", "shall",
    "get", "got", "make", "made", "take", "took", "come", "go", "see", "look",
    "give", "know", "think", "tell", "let", "us", "li", "ul", "br", "strong",
    "nbsp", "amp", "quot", "one", "two", "three", "day", "days", "night", "nights",
    "hotel", "accommodation", "breakfast", "included", "including", "includes",
    "per", "person", "package", "trip", "travel", "journey", "experience",
})


def _strip_html(text: str) -> str:
    """Remove HTML tags."""
    return re.sub(r"<[^>]+>", " ", text)


def _tokenize(text: str) -> List[str]:
    """Tokenize to lowercase alpha words, remove stop words and short words."""
    clean = _strip_html(text)
    words = re.findall(r"[a-z]{3,}", clean.lower())
    return [w for w in words if w not in _STOP_WORDS]


# ---------------------------------------------------------------------------
# TF-IDF Vector Builder
# ---------------------------------------------------------------------------

class TFIDFVectorizer:
    """Builds TF-IDF vectors. Vocabulary limited to top N terms for efficiency."""

    def __init__(self, max_vocab: int = 600):
        self.max_vocab = max_vocab
        self.vocab: Dict[str, int] = {}        # term -> index
        self.idf: Dict[str, float] = {}        # term -> IDF score
        self.doc_count: int = 0

    def fit(self, documents: List[str]) -> "TFIDFVectorizer":
        """Build vocabulary and IDF from documents."""
        self.doc_count = len(documents)
        if self.doc_count == 0:
            return self

        # Count document frequency for each term
        df: Counter = Counter()
        for doc in documents:
            unique_terms = set(_tokenize(doc))
            df.update(unique_terms)

        # Keep top N by doc frequency (most informative terms)
        # Exclude terms appearing in >80% or <2 docs (too common/rare)
        max_df = self.doc_count * 0.8
        min_df = 2
        filtered = {
            term: freq for term, freq in df.items()
            if min_df <= freq <= max_df
        }

        # Take top N most frequent
        top_terms = sorted(filtered.items(), key=lambda x: x[1], reverse=True)[:self.max_vocab]
        self.vocab = {term: i for i, (term, _) in enumerate(top_terms)}

        # Compute IDF: log(N / df(t))
        self.idf = {}
        for term, idx in self.vocab.items():
            doc_freq = df[term]
            self.idf[term] = math.log((self.doc_count + 1) / (doc_freq + 1)) + 1

        logger.info(f"TF-IDF vocabulary built: {len(self.vocab)} terms from {self.doc_count} documents")
        return self

    def transform(self, text: str) -> Dict[str, float]:
        """Convert text to sparse TF-IDF vector {term: weight}."""
        tokens = _tokenize(text)
        if not tokens:
            return {}

        tf = Counter(tokens)
        max_tf = max(tf.values()) if tf else 1

        vector: Dict[str, float] = {}
        for term, count in tf.items():
            if term in self.vocab:
                # Normalized TF * IDF
                tf_norm = 0.5 + 0.5 * (count / max_tf)
                vector[term] = round(tf_norm * self.idf[term], 4)

        return vector

    def to_json(self) -> str:
        """Serialize vectorizer state."""
        return json.dumps({
            "vocab": self.vocab,
            "idf": self.idf,
            "doc_count": self.doc_count,
        })

    @classmethod
    def from_json(cls, data: str) -> "TFIDFVectorizer":
        """Deserialize vectorizer state."""
        obj = json.loads(data)
        v = cls()
        v.vocab = obj["vocab"]
        v.idf = {k: float(val) for k, val in obj["idf"].items()}
        v.doc_count = obj["doc_count"]
        return v


# ---------------------------------------------------------------------------
# Cosine similarity for sparse vectors
# ---------------------------------------------------------------------------

def cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """Cosine similarity between two sparse TF-IDF vectors. Returns 0.0-1.0."""
    if not vec_a or not vec_b:
        return 0.0

    # Compute dot product only on shared terms
    shared = set(vec_a.keys()) & set(vec_b.keys())
    if not shared:
        return 0.0

    dot = sum(vec_a[t] * vec_b[t] for t in shared)
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# Vector Store (PostgreSQL-backed)
# ---------------------------------------------------------------------------

# Module-level cache for vectorizer (loaded once)
_vectorizer_cache: Optional[TFIDFVectorizer] = None
# Module-level cache for all vectors (loaded once, avoids per-query DB fetch)
_vectors_cache: Optional[List[Tuple[int, Dict[str, float]]]] = None
_vectors_cache_ts: float = 0.0
_VECTORS_CACHE_TTL = 300  # 5 minutes

# RAG search result cache (TTL-based)
_search_cache: Dict[str, List[Tuple[int, float]]] = {}
_search_cache_ts: Dict[str, float] = {}
_SEARCH_CACHE_TTL = 120  # 2 minutes


class VectorStore:
    """
    Database-backed TF-IDF vector store for RAG retrieval.
    Pre-computes and stores package vectors. Enables semantic search.
    Supports both SQLite and PostgreSQL.
    """

    TABLE_DDL = """
    CREATE TABLE IF NOT EXISTS package_vectors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        package_id INTEGER UNIQUE NOT NULL,
        text_content TEXT,
        vector TEXT NOT NULL DEFAULT '{}'
    );
    """

    INDEX_DDL = """CREATE INDEX IF NOT EXISTS idx_pkg_vec_pid ON package_vectors(package_id);"""

    VECTORIZER_DDL = """
    CREATE TABLE IF NOT EXISTS vectorizer_state (
        id INTEGER PRIMARY KEY DEFAULT 1,
        state TEXT NOT NULL,
        built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    def __init__(self, db: Session):
        self.db = db

    def ensure_tables(self):
        """Create tables if they don't exist."""
        self.db.execute(text(self.TABLE_DDL))
        self.db.execute(text(self.INDEX_DDL))
        self.db.execute(text(self.VECTORIZER_DDL))
        self.db.commit()

    def build_index(self) -> int:
        """
        Build TF-IDF vectors for all packages and store in DB.
        Returns number of packages indexed.
        """
        start = time.time()
        self.ensure_tables()

        # Fetch all package text
        rows = self.db.execute(text("""
            SELECT id, external_name, description, highlights, triptype,
                   included_countries, included_cities, included_regions,
                   start_location, end_location, route
            FROM rag_packages
        """)).fetchall()

        if not rows:
            logger.warning("No packages found to index")
            return 0

        # Build document text for each package
        docs: List[str] = []
        pkg_ids: List[int] = []
        pkg_texts: List[str] = []

        for row in rows:
            pid = row[0]
            parts = [str(field or "") for field in row[1:]]
            # Replace pipes with spaces
            combined = " ".join(parts).replace("|", " ")
            docs.append(combined)
            pkg_ids.append(pid)
            pkg_texts.append(combined[:1000])  # Store truncated text

        # Fit vectorizer
        vectorizer = TFIDFVectorizer(max_vocab=600)
        vectorizer.fit(docs)

        # Clear old data
        self.db.execute(text("DELETE FROM package_vectors"))
        self.db.execute(text("DELETE FROM vectorizer_state"))

        # Transform and store
        batch_size = 100
        count = 0
        for i in range(0, len(docs), batch_size):
            batch_docs = docs[i:i + batch_size]
            batch_ids = pkg_ids[i:i + batch_size]
            batch_texts = pkg_texts[i:i + batch_size]

            for doc, pid, txt in zip(batch_docs, batch_ids, batch_texts):
                vec = vectorizer.transform(doc)
                self.db.execute(text(
                    "INSERT INTO package_vectors (package_id, text_content, vector) "
                    "VALUES (:pid, :txt, :vec)"
                ), {"pid": pid, "txt": txt, "vec": json.dumps(vec)})
                count += 1

            self.db.commit()

        # Store vectorizer state
        self.db.execute(text(
            "INSERT INTO vectorizer_state (id, state) VALUES (1, :state)"
        ), {"state": vectorizer.to_json()})
        self.db.commit()

        # Update module cache
        global _vectorizer_cache
        _vectorizer_cache = vectorizer

        # Invalidate vector and search caches after rebuild
        global _vectors_cache, _vectors_cache_ts, _search_cache, _search_cache_ts
        _vectors_cache = None
        _vectors_cache_ts = 0.0
        _search_cache = {}
        _search_cache_ts = {}

        elapsed = (time.time() - start) * 1000
        logger.info(f"Vector index built: {count} packages in {elapsed:.0f}ms, "
                    f"vocab size: {len(vectorizer.vocab)}")
        return count

    def _get_vectorizer(self) -> Optional[TFIDFVectorizer]:
        """Load vectorizer from cache or DB."""
        global _vectorizer_cache
        if _vectorizer_cache is not None:
            return _vectorizer_cache

        try:
            row = self.db.execute(text(
                "SELECT state FROM vectorizer_state WHERE id = 1"
            )).fetchone()
            if row:
                _vectorizer_cache = TFIDFVectorizer.from_json(row[0] if isinstance(row[0], str) else json.dumps(row[0]))
                return _vectorizer_cache
        except Exception as e:
            logger.warning(f"Could not load vectorizer: {e}")
        return None

    def semantic_search(
        self,
        query_text: str,
        top_k: int = 30,
    ) -> List[Tuple[int, float]]:
        """
        RAG retrieval: find top_k packages most similar to query_text.
        Returns list of (package_id, similarity_score) sorted desc.
        Uses in-memory vector cache and search result cache for speed.
        """
        global _vectors_cache, _vectors_cache_ts, _search_cache, _search_cache_ts

        vectorizer = self._get_vectorizer()
        if not vectorizer:
            logger.warning("Vectorizer not loaded, falling back to empty results")
            return []

        # Check search result cache
        cache_key = query_text.lower().strip()[:200]
        if cache_key in _search_cache and (time.time() - _search_cache_ts.get(cache_key, 0)) < _SEARCH_CACHE_TTL:
            logger.info(f"RAG search cache hit for '{cache_key[:50]}...'")
            return _search_cache[cache_key][:top_k]

        start = time.time()

        # Vectorize query
        query_vec = vectorizer.transform(query_text)
        if not query_vec:
            return []

        # Load vectors from memory cache or DB (avoids per-query DB round-trip)
        now = time.time()
        if _vectors_cache is None or (now - _vectors_cache_ts) > _VECTORS_CACHE_TTL:
            rows = self.db.execute(text(
                "SELECT package_id, vector FROM package_vectors"
            )).fetchall()
            _vectors_cache = []
            for pkg_id, vec_data in rows:
                stored_vec = vec_data if isinstance(vec_data, dict) else json.loads(vec_data)
                _vectors_cache.append((pkg_id, stored_vec))
            _vectors_cache_ts = now
            logger.info(f"Loaded {len(_vectors_cache)} vectors into memory cache")

        # Compute similarity against cached vectors
        results: List[Tuple[int, float]] = []
        for pkg_id, stored_vec in _vectors_cache:
            sim = cosine_similarity(query_vec, stored_vec)
            if sim > 0.05:  # threshold to reduce noise
                results.append((pkg_id, sim))

        # Sort by similarity desc
        results.sort(key=lambda x: x[1], reverse=True)

        # Cache search results
        _search_cache[cache_key] = results
        _search_cache_ts[cache_key] = time.time()
        # Evict old cache entries (keep max 100)
        if len(_search_cache) > 100:
            oldest_key = min(_search_cache_ts.keys(), key=lambda k: _search_cache_ts[k])
            _search_cache.pop(oldest_key, None)
            _search_cache_ts.pop(oldest_key, None)

        elapsed = (time.time() - start) * 1000
        logger.info(f"RAG search: '{query_text[:50]}...' -> {len(results)} hits in {elapsed:.0f}ms")

        return results[:top_k]

    def is_ready(self) -> bool:
        """Check if vector index exists."""
        try:
            row = self.db.execute(text(
                "SELECT COUNT(*) FROM package_vectors"
            )).fetchone()
            return (row[0] or 0) > 0 if row is not None else False
        except Exception:
            return False
