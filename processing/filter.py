"""
Filter pipeline entry point.

Combines deduplication, memory enrichment, and ranking into a single
`filter_and_rank()` call used by main.py. The actual logic lives in ranker.py.
"""

from typing import List
import logging

from collectors import ContentItem
from processing.ranker import deduplicate, rank_items

logger = logging.getLogger(__name__)


def filter_and_rank(
    items: List[ContentItem], max_items: int = 15
) -> List[ContentItem]:
    """Full pipeline: deduplicate → enrich with memory → rank → return top N."""
    deduped = deduplicate(items)

    # Attach novelty + preference scores from ChromaDB (no-op if unavailable)
    try:
        from memory.chroma_store import get_novelty_and_preference
        item_dicts = [i.to_dict() for i in deduped]
        enriched = get_novelty_and_preference(item_dicts)
        # Write scores back onto the ContentItem objects as dynamic attributes
        for item, d in zip(deduped, enriched):
            item._novelty_score = d.get("novelty_score", 1.0)
            item._pref_score = d.get("pref_score", 0.0)
    except Exception as e:
        logger.debug(f"Memory enrichment skipped: {e}")

    ranked = rank_items(deduped, max_items)
    return ranked
