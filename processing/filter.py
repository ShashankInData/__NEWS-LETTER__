from typing import List
from urllib.parse import urlparse
import logging

from collectors import ContentItem

logger = logging.getLogger(__name__)


def deduplicate(items: List[ContentItem]) -> List[ContentItem]:
    """Remove duplicate items based on URL similarity and title overlap."""
    seen_urls = set()
    seen_titles = set()
    unique = []

    for item in items:
        # Normalize URL
        parsed = urlparse(item.url)
        normalized_url = f"{parsed.netloc}{parsed.path}".rstrip("/").lower()

        # Normalize title (first 60 chars, lowered)
        normalized_title = item.title[:60].lower().strip()

        if normalized_url in seen_urls or normalized_title in seen_titles:
            continue

        seen_urls.add(normalized_url)
        seen_titles.add(normalized_title)
        unique.append(item)

    removed = len(items) - len(unique)
    if removed:
        logger.info(f"Dedup: removed {removed} duplicates, {len(unique)} remaining")
    return unique


def rank_items(items: List[ContentItem], max_items: int = 15) -> List[ContentItem]:
    """
    Rank items by relevance score:
    - More matched topic tags = higher
    - Higher engagement (score/comments) = higher
    - Prefer diverse sources
    """
    for item in items:
        # Relevance score
        item._rank_score = (
            len(item.tags_matched) * 10  # topic relevance
            + min(item.score, 500) / 50  # engagement (capped)
            + min(item.comments, 100) / 20  # discussion activity
        )

    # Sort by rank score descending
    ranked = sorted(items, key=lambda x: x._rank_score, reverse=True)

    # Ensure source diversity: don't let one source dominate
    source_counts = {}
    max_per_source = max(max_items // 3, 3)  # at least 3 per source
    diverse = []

    for item in ranked:
        source_key = item.source
        count = source_counts.get(source_key, 0)
        if count < max_per_source:
            diverse.append(item)
            source_counts[source_key] = count + 1
        if len(diverse) >= max_items:
            break

    # If we didn't fill up, add remaining items regardless of source
    if len(diverse) < max_items:
        remaining = [i for i in ranked if i not in diverse]
        diverse.extend(remaining[: max_items - len(diverse)])

    logger.info(f"Ranked: returning top {len(diverse)} items")
    return diverse


def filter_and_rank(
    items: List[ContentItem], max_items: int = 15
) -> List[ContentItem]:
    """Full pipeline: deduplicate → rank → return top N."""
    deduped = deduplicate(items)
    ranked = rank_items(deduped, max_items)
    return ranked
