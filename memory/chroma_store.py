"""
ChromaDB memory store for AI Pulse.

Two responsibilities:
1. Content history — embed + store every item after each run so future
   runs can check novelty ("have we seen something like this before?")

2. Preference scores — when the user taps 👍/👎 on Telegram, the score
   for that item's embedding cluster is updated here. rank_items() reads
   these scores to personalise the ranking.

Collections:
  content_history  — documents: item titles, metadata: source/url/date
  preferences      — documents: item titles, metadata: score (float -1..+1)

Embeddings: sentence-transformers/all-MiniLM-L6-v2 via HuggingFace
  — runs locally, no API key, no cost.
"""

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Lazy imports so the app still starts if chromadb/sentence-transformers
# aren't installed yet (they'll just skip the memory layer).
_chroma_client = None
_embedder = None

DB_PATH = Path(__file__).parent / "db"
HISTORY_COLLECTION = "content_history"
PREF_COLLECTION = "preferences"

# How many similar past items to retrieve for novelty/preference checks
N_SIMILAR = 5


def _get_client():
    global _chroma_client
    if _chroma_client is None:
        try:
            import chromadb
            _chroma_client = chromadb.PersistentClient(path=str(DB_PATH))
        except ImportError:
            logger.warning("chromadb not installed — memory layer disabled. Run: pip install chromadb")
    return _chroma_client


def _get_embedder():
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        except ImportError:
            logger.warning("sentence-transformers not installed — memory layer disabled. Run: pip install sentence-transformers")
    return _embedder


def _embed(texts: List[str]) -> Optional[List[List[float]]]:
    embedder = _get_embedder()
    if embedder is None:
        return None
    return embedder.encode(texts, show_progress_bar=False).tolist()


def _item_id(title: str, url: str) -> str:
    """Stable ID for a content item — hash of url, fallback to title."""
    raw = url.strip() if url.strip() else title.strip()
    return hashlib.md5(raw.encode()).hexdigest()


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def store_items(items: List[dict]) -> None:
    """
    Embed and store a list of summarized items in content_history.
    Called once per pipeline run, after DELIVER.

    items: list of dicts with keys title, url, source, summary, tags
    """
    client = _get_client()
    if client is None:
        return

    texts = [f"{i.get('title', '')} {i.get('summary', '')}" for i in items]
    embeddings = _embed(texts)
    if embeddings is None:
        return

    try:
        col = client.get_or_create_collection(HISTORY_COLLECTION)
        ids = [_item_id(i.get("title", ""), i.get("url", "")) for i in items]
        metadatas = [
            {
                "title": i.get("title", "")[:200],
                "source": i.get("source", ""),
                "url": i.get("url", "")[:500],
                "stored_at": datetime.now(timezone.utc).isoformat(),
                "tags": ",".join(i.get("tags", [])),
            }
            for i in items
        ]
        col.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        logger.info(f"Memory: stored {len(items)} items in content_history")
    except Exception as e:
        logger.warning(f"Memory: store_items failed — {e}")


def get_novelty_and_preference(items: List[dict]) -> List[dict]:
    """
    For each item, query ChromaDB for similar past content and return
    two extra fields attached to the item dict:
      - novelty_score   float 0..1  (1 = never seen anything like this)
      - pref_score      float -1..1 (positive = user historically liked similar)

    If the memory layer is unavailable, returns items unchanged.
    """
    client = _get_client()
    if client is None:
        return items

    texts = [f"{i.get('title', '')} {i.get('summary', i.get('content', ''))}" for i in items]
    embeddings = _embed(texts)
    if embeddings is None:
        return items

    try:
        history_col = client.get_or_create_collection(HISTORY_COLLECTION)
        pref_col = client.get_or_create_collection(PREF_COLLECTION)

        history_count = history_col.count()
        pref_count = pref_col.count()

        for item, embedding in zip(items, embeddings):
            # ── Novelty ──────────────────────────────────────────
            if history_count >= 1:
                n = min(N_SIMILAR, history_count)
                results = history_col.query(
                    query_embeddings=[embedding], n_results=n, include=["distances"]
                )
                distances = results["distances"][0]  # lower = more similar
                # Convert distance to novelty: avg distance capped at 1.0
                avg_dist = sum(distances) / len(distances) if distances else 1.0
                novelty = min(avg_dist, 1.0)
            else:
                novelty = 1.0  # first run — everything is novel

            # ── Preference ───────────────────────────────────────
            if pref_count >= 1:
                n = min(N_SIMILAR, pref_count)
                results = pref_col.query(
                    query_embeddings=[embedding], n_results=n,
                    include=["distances", "metadatas"]
                )
                distances = results["distances"][0]
                metadatas = results["metadatas"][0]

                if distances:
                    # Weighted average preference: closer items count more
                    weights = [1.0 / (d + 1e-6) for d in distances]
                    scores = [float(m.get("score", 0.0)) for m in metadatas]
                    weighted_pref = sum(w * s for w, s in zip(weights, scores)) / sum(weights)
                else:
                    weighted_pref = 0.0
            else:
                weighted_pref = 0.0

            item["novelty_score"] = round(novelty, 4)
            item["pref_score"] = round(weighted_pref, 4)

    except Exception as e:
        logger.warning(f"Memory: get_novelty_and_preference failed — {e}")
        for item in items:
            item.setdefault("novelty_score", 1.0)
            item.setdefault("pref_score", 0.0)

    return items


def record_feedback(item_id: str, title: str, score: float) -> None:
    """
    Store a preference signal from a 👍/👎 button tap.

    score: +1.0 for thumbs up, -1.0 for thumbs down.

    The item must already be in content_history (it was stored after
    the run that sent it). We re-embed the title and upsert into
    preferences so future runs pick it up.
    """
    client = _get_client()
    if client is None:
        logger.warning("Memory: record_feedback called but chromadb unavailable")
        return

    embeddings = _embed([title])
    if embeddings is None:
        return

    try:
        col = client.get_or_create_collection(PREF_COLLECTION)
        col.upsert(
            ids=[item_id],
            embeddings=embeddings,
            documents=[title],
            metadatas=[{"score": score, "title": title[:200], "updated_at": datetime.now(timezone.utc).isoformat()}],
        )
        label = "👍 +1.0" if score > 0 else "👎 -1.0"
        logger.info(f"Memory: preference recorded {label} for '{title[:60]}'")
    except Exception as e:
        logger.warning(f"Memory: record_feedback failed — {e}")
