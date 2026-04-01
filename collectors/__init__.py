from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class ContentItem:
    """A single piece of content scraped from any source."""
    title: str
    url: str
    source: str  # "reddit", "twitter", "arxiv", "huggingface", "tech_blog"
    subreddit_or_account: str  # e.g. "r/MachineLearning" or "@ylecun"
    content: str  # body text, abstract, or tweet text
    score: int = 0  # upvotes, likes, etc.
    comments: int = 0
    published_at: Optional[datetime] = None
    tags_matched: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "subreddit_or_account": self.subreddit_or_account,
            "content": self.content[:500],  # truncate for summarization
            "score": self.score,
            "comments": self.comments,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "tags_matched": self.tags_matched,
        }


class BaseCollector(ABC):
    """Abstract base for all content collectors."""

    def __init__(self, config: dict, topic_tags: List[str]):
        self.config = config
        self.topic_tags = [tag.lower() for tag in topic_tags]

    @abstractmethod
    def collect(self) -> List[ContentItem]:
        """Scrape and return raw content items."""
        pass

    def matches_topics(self, text: str) -> List[str]:
        """Check if text matches any topic tags. Returns matched tags."""
        text_lower = text.lower()
        matched = []
        for tag in self.topic_tags:
            if tag in text_lower:
                matched.append(tag)
        return matched
