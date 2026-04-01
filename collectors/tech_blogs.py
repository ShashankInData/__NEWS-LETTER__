import feedparser
from datetime import datetime, timezone
from time import mktime
from typing import List
import logging

from collectors import BaseCollector, ContentItem

logger = logging.getLogger(__name__)


class TechBlogCollector(BaseCollector):
    """Collects posts from tech company blogs via RSS feeds."""

    # Mapping of known domains to friendly names
    BLOG_NAMES = {
        "openai.com": "OpenAI",
        "anthropic.com": "Anthropic",
        "blog.google": "Google AI",
        "ai.meta.com": "Meta AI",
        "mistral.ai": "Mistral AI",
        "deepmind.google": "Google DeepMind",
    }

    def __init__(self, config: dict, topic_tags: List[str]):
        super().__init__(config, topic_tags)
        self.rss_feeds = config.get("rss_feeds", [])

    def _get_blog_name(self, feed_url: str) -> str:
        for domain, name in self.BLOG_NAMES.items():
            if domain in feed_url:
                return name
        return feed_url

    def collect(self) -> List[ContentItem]:
        items = []

        for feed_url in self.rss_feeds:
            blog_name = self._get_blog_name(feed_url)
            logger.info(f"Parsing RSS: {blog_name} ({feed_url})")

            try:
                feed = feedparser.parse(feed_url)

                if feed.bozo and not feed.entries:
                    logger.warning(f"Feed parse error for {blog_name}: {feed.bozo_exception}")
                    continue

                for entry in feed.entries[:10]:  # Last 10 posts
                    title = entry.get("title", "")
                    summary = entry.get("summary", entry.get("description", ""))
                    link = entry.get("link", "")

                    full_text = f"{title} {summary}"
                    matched_tags = self.matches_topics(full_text)

                    if not matched_tags:
                        continue

                    # Parse published date
                    published_at = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        try:
                            published_at = datetime.fromtimestamp(
                                mktime(entry.published_parsed), tz=timezone.utc
                            )
                        except (TypeError, ValueError, OverflowError):
                            pass
                    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                        try:
                            published_at = datetime.fromtimestamp(
                                mktime(entry.updated_parsed), tz=timezone.utc
                            )
                        except (TypeError, ValueError, OverflowError):
                            pass

                    # Strip HTML tags from summary (basic)
                    import re
                    clean_summary = re.sub(r"<[^>]+>", "", summary)

                    item = ContentItem(
                        title=title.strip(),
                        url=link,
                        source="tech_blog",
                        subreddit_or_account=blog_name,
                        content=clean_summary[:1000].strip(),
                        score=0,
                        comments=0,
                        published_at=published_at,
                        tags_matched=matched_tags,
                    )
                    items.append(item)

            except Exception as e:
                logger.error(f"Failed to parse RSS for {blog_name}: {e}")

        logger.info(f"Tech Blogs: collected {len(items)} matching posts")
        return items
