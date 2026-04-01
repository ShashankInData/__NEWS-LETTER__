import arxiv
import requests
from datetime import datetime, timezone, timedelta
from typing import List
import logging

from collectors import BaseCollector, ContentItem

logger = logging.getLogger(__name__)


class ArxivCollector(BaseCollector):
    """Collects recent papers from arXiv matching topic tags."""

    def __init__(self, config: dict, topic_tags: List[str]):
        super().__init__(config, topic_tags)
        self.categories = config.get("categories", ["cs.AI", "cs.CL", "cs.LG"])
        self.max_results = config.get("max_results", 30)

    def collect(self) -> List[ContentItem]:
        items = []

        # Build query: search across categories
        cat_query = " OR ".join([f"cat:{cat}" for cat in self.categories])

        logger.info(f"Searching arXiv: {cat_query} (max {self.max_results})")

        try:
            client = arxiv.Client()
            search = arxiv.Search(
                query=cat_query,
                max_results=self.max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending,
            )

            for result in client.results(search):
                full_text = f"{result.title} {result.summary}"
                matched_tags = self.matches_topics(full_text)

                if not matched_tags:
                    continue

                item = ContentItem(
                    title=result.title.replace("\n", " ").strip(),
                    url=result.entry_id,
                    source="arxiv",
                    subreddit_or_account=", ".join(
                        [cat if isinstance(cat, str) else cat.term for cat in result.categories[:3]]
                    ),
                    content=result.summary[:1000].replace("\n", " ").strip(),
                    score=0,
                    comments=0,
                    published_at=result.published.replace(tzinfo=timezone.utc)
                    if result.published.tzinfo is None
                    else result.published,
                    tags_matched=matched_tags,
                )
                items.append(item)

        except Exception as e:
            logger.error(f"Failed to search arXiv: {e}")

        logger.info(f"arXiv: collected {len(items)} matching papers")
        return items


class HuggingFaceCollector(BaseCollector):
    """Collects daily papers from HuggingFace."""

    HF_PAPERS_API = "https://huggingface.co/api/daily_papers"

    def __init__(self, config: dict, topic_tags: List[str]):
        super().__init__(config, topic_tags)

    def collect(self) -> List[ContentItem]:
        items = []
        logger.info("Fetching HuggingFace daily papers")

        try:
            resp = requests.get(self.HF_PAPERS_API, timeout=15)
            resp.raise_for_status()
            papers = resp.json()

            for paper in papers:
                paper_data = paper.get("paper", {})
                title = paper_data.get("title", "")
                summary = paper_data.get("summary", "")
                paper_id = paper_data.get("id", "")

                full_text = f"{title} {summary}"
                matched_tags = self.matches_topics(full_text)

                if not matched_tags:
                    continue

                published_str = paper.get("publishedAt")
                published_at = None
                if published_str:
                    try:
                        published_at = datetime.fromisoformat(
                            published_str.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        published_at = datetime.now(timezone.utc)

                item = ContentItem(
                    title=title.replace("\n", " ").strip(),
                    url=f"https://huggingface.co/papers/{paper_id}",
                    source="huggingface",
                    subreddit_or_account="HF Daily Papers",
                    content=summary[:1000].replace("\n", " ").strip(),
                    score=paper.get("numLikes", 0),
                    comments=paper.get("numComments", 0),
                    published_at=published_at,
                    tags_matched=matched_tags,
                )
                items.append(item)

        except Exception as e:
            logger.error(f"Failed to fetch HuggingFace papers: {e}")

        logger.info(f"HuggingFace: collected {len(items)} matching papers")
        return items
