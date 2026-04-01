import praw
from datetime import datetime, timezone
from typing import List
import logging

from collectors import BaseCollector, ContentItem

logger = logging.getLogger(__name__)


class RedditCollector(BaseCollector):
    """Collects top posts from configured subreddits using PRAW."""

    def __init__(self, config: dict, topic_tags: List[str]):
        super().__init__(config, topic_tags)
        self.reddit = praw.Reddit(
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            user_agent=config["user_agent"],
        )
        self.subreddits = config.get("subreddits", ["MachineLearning"])
        self.top_n = config.get("top_n", 20)
        self.time_filter = config.get("time_filter", "week")

    def collect(self) -> List[ContentItem]:
        items = []

        for sub_name in self.subreddits:
            logger.info(f"Scraping r/{sub_name} (top {self.top_n}, {self.time_filter})")
            try:
                subreddit = self.reddit.subreddit(sub_name)
                for post in subreddit.top(
                    time_filter=self.time_filter, limit=self.top_n
                ):
                    # Combine title + selftext for topic matching
                    full_text = f"{post.title} {post.selftext or ''}"
                    matched_tags = self.matches_topics(full_text)

                    # Only include if it matches at least one topic tag
                    if not matched_tags:
                        continue

                    item = ContentItem(
                        title=post.title,
                        url=f"https://reddit.com{post.permalink}",
                        source="reddit",
                        subreddit_or_account=f"r/{sub_name}",
                        content=post.selftext[:1000] if post.selftext else "",
                        score=post.score,
                        comments=post.num_comments,
                        published_at=datetime.fromtimestamp(
                            post.created_utc, tz=timezone.utc
                        ),
                        tags_matched=matched_tags,
                    )
                    items.append(item)
                    logger.debug(
                        f"  Matched: {post.title[:80]}... [{', '.join(matched_tags)}]"
                    )

            except Exception as e:
                logger.error(f"Failed to scrape r/{sub_name}: {e}")

        logger.info(f"Reddit: collected {len(items)} matching posts")
        return items
