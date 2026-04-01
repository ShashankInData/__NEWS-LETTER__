"""
Ranking and deduplication logic for collected content items.

Responsible for:
- Deduplicating items across sources (URL + title similarity)
- Scoring items by relevance (topic tag matches) + engagement (score, comments)
- Incorporating novelty + user preference signals from ChromaDB (when available)
- Enforcing source diversity so no single source dominates the digest
"""

from typing import List
from urllib.parse import urlparse
import logging

from collectors import ContentItem

logger = logging.getLogger(__name__)

# Weights for the composite rank score
W_TOPIC = 10     # per matched tag
W_ENGAGE = 1/50  # upvotes, capped at 500
W_COMMENT = 1/20 # comments, capped at 100
W_NOVELTY = 8    # max bonus for a completely unseen topic
W_PREF = 12      # max bonus/penalty for strong user preference signal


def deduplicate(items: List[ContentItem]) -> List[ContentItem]:
    """
    Remove duplicate items based on URL similarity and title overlap.

    Two items are considered duplicates if they share the same normalised URL
    or if their titles are identical within the first 60 characters.
    """
    seen_urls = set()
    seen_titles = set()
    unique = []

    for item in items:
        # Normalise URL: strip scheme, trailing slashes, lowercase
        parsed = urlparse(item.url)
        normalized_url = f"{parsed.netloc}{parsed.path}".rstrip("/").lower()

        # Normalise title: first 60 chars, lowercased
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
    Rank items by a composite relevance score, then apply source diversity.

    Scoring formula per item:
      - +10 per matched topic tag         (topic relevance)
      - +engagement score / 50            (capped at 500 upvotes)
      - +comment count / 20               (capped at 100 comments)
      - +novelty_score * 8                (0 if seen before, up to +8 if novel)
      - +pref_score * 12                  (-12..+12 based on past 👍/👎 feedback)

    novelty_score and pref_score are attached by memory.chroma_store if
    ChromaDB is available. If not present they default to neutral values
    (novelty=1.0, pref=0.0) so scoring degrades gracefully to the old formula.

    After ranking, a source-diversity cap is applied so that no single source
    (e.g. Reddit) takes more than ~1/3 of the total slots.
    If the diversity pass leaves empty slots, remaining items fill them.
    """
    for item in items:
        novelty = getattr(item, "_novelty_score", 1.0)  # 1.0 = fully novel (no history yet)
        pref = getattr(item, "_pref_score", 0.0)        # 0.0 = no preference signal yet

        item._rank_score = (
            len(item.tags_matched) * W_TOPIC
            + min(item.score, 500) * W_ENGAGE
            + min(item.comments, 100) * W_COMMENT
            + novelty * W_NOVELTY
            + pref * W_PREF
        )

    # Sort by rank score descending
    ranked = sorted(items, key=lambda x: x._rank_score, reverse=True)

    # Source diversity: no single source dominates
    source_counts: dict = {}
    max_per_source = max(max_items // 3, 3)  # at least 3 slots per source
    diverse: List[ContentItem] = []

    for item in ranked:
        count = source_counts.get(item.source, 0)
        if count < max_per_source:
            diverse.append(item)
            source_counts[item.source] = count + 1
        if len(diverse) >= max_items:
            break

    # Back-fill if diversity pass left empty slots
    if len(diverse) < max_items:
        remaining = [i for i in ranked if i not in diverse]
        diverse.extend(remaining[: max_items - len(diverse)])

    logger.info(
        f"Ranked: returning top {len(diverse)} items "
        f"(sources: {dict(source_counts)})"
    )
    return diverse
