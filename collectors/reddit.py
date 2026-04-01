import feedparser
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List
import logging

from collectors import BaseCollector, ContentItem

logger = logging.getLogger(__name__)


class RedditCollector(BaseCollector):
    """Collects top posts from configured subreddits using public RSS feeds."""

    def __init__(self, config: dict, topic_tags: List[str]):
        super().__init__(config, topic_tags)
        self.subreddits = config.get("subreddits", ["MachineLearning"])
        self.top_n = config.get("top_n", 20)
        self.time_filter = config.get("time_filter", "week")

    def collect(self) -> List[ContentItem]:
        items = []

        for sub_name in self.subreddits:
            logger.info(f"Scraping r/{sub_name} (top {self.top_n}, {self.time_filter})")
            rss_url = f"https://www.reddit.com/r/{sub_name}/top.rss?t={self.time_filter}&limit={self.top_n}"
            try:
                feed = feedparser.parse(rss_url)
                if feed.bozo and not feed.entries:
                    logger.warning(f"r/{sub_name}: RSS parse error — {feed.bozo_exception}")
                    continue

                for entry in feed.entries:
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")
                    full_text = f"{title} {summary}"
                    matched_tags = self.matches_topics(full_text)

                    if not matched_tags:
                        continue

                    published_at = None
                    if entry.get("published"):
                        try:
                            published_at = parsedate_to_datetime(entry.published).astimezone(timezone.utc)
                        except Exception:
                            pass

                    item = ContentItem(
                        title=title,
                        url=entry.get("link", ""),
                        source="reddit",
                        subreddit_or_account=f"r/{sub_name}",
                        content=summary[:1000],
                        score=0,
                        comments=0,
                        published_at=published_at,
                        tags_matched=matched_tags,
                    )
                    items.append(item)
                    logger.debug(f"  Matched: {title[:80]}... [{', '.join(matched_tags)}]")

            except Exception as e:
                logger.error(f"Failed to scrape r/{sub_name}: {e}")

        logger.info(f"Reddit: collected {len(items)} matching posts")
        return items
