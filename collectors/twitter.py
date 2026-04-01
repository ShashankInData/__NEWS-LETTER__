import requests
from datetime import datetime, timezone
from typing import List
import logging

from collectors import BaseCollector, ContentItem

logger = logging.getLogger(__name__)


class TwitterCollector(BaseCollector):
    """
    Collects tweets from configured accounts.

    Methods:
    - apify: Uses Apify Twitter Scraper actor (paid, reliable)
    - nitter_rss: Uses Nitter RSS endpoints (free, can be flaky)
    """

    def __init__(self, config: dict, topic_tags: List[str], apify_token: str = None):
        super().__init__(config, topic_tags)
        self.method = config.get("method", "apify")
        self.accounts = config.get("accounts", [])
        self.search_terms = config.get("search_terms", [])
        self.apify_token = apify_token

    def collect(self) -> List[ContentItem]:
        if self.method == "apify" and self.apify_token:
            return self._collect_apify()
        elif self.method == "nitter_rss":
            return self._collect_nitter()
        else:
            logger.warning(
                f"Twitter method '{self.method}' not available "
                f"(apify_token={'set' if self.apify_token else 'missing'}). "
                f"Skipping Twitter collection."
            )
            return []

    def _collect_apify(self) -> List[ContentItem]:
        """
        Uses Apify's Twitter Scraper actor.
        Docs: https://apify.com/apidojo/twitter-scraper

        You need to:
        1. Sign up at apify.com
        2. Find the Twitter Scraper actor
        3. Use the actor API to run it with your search terms
        """
        items = []
        logger.info(f"Collecting tweets via Apify for {len(self.accounts)} accounts")

        # Apify actor run endpoint
        ACTOR_ID = "kaitoeasyapi~twitter-x-data-tweet-scraper-pay-per-result-cheapest"
        RUN_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs"

        try:
            # Build search queries from accounts and terms
            search_queries = []
            for account in self.accounts:
                account_clean = account.lstrip("@")
                search_queries.append(f"from:{account_clean}")
            for term in self.search_terms:
                search_queries.append(term)

            payload = {
                "searchTerms": search_queries,
                "maxTweets": 50,
                "sort": "Top",
            }

            resp = requests.post(
                RUN_URL,
                json=payload,
                params={"token": self.apify_token, "waitForFinish": 120},
                timeout=180,
            )

            if resp.status_code != 201:
                logger.error(f"Apify run failed: {resp.status_code} {resp.text[:200]}")
                return items

            run_data = resp.json()
            dataset_id = run_data.get("data", {}).get("defaultDatasetId")

            if not dataset_id:
                logger.error("No dataset ID returned from Apify run")
                return items

            # Fetch results
            dataset_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
            dataset_resp = requests.get(
                dataset_url,
                params={"token": self.apify_token, "format": "json"},
                timeout=30,
            )
            tweets = dataset_resp.json()

            for tweet in tweets:
                text = tweet.get("text", tweet.get("full_text", ""))
                user = tweet.get("user", {}).get("screen_name", "unknown")

                matched_tags = self.matches_topics(text)
                if not matched_tags:
                    continue

                published_at = None
                created = tweet.get("created_at")
                if created:
                    try:
                        published_at = datetime.strptime(
                            created, "%a %b %d %H:%M:%S %z %Y"
                        )
                    except (ValueError, TypeError):
                        pass

                item = ContentItem(
                    title=text[:120].replace("\n", " ") + "...",
                    url=f"https://twitter.com/{user}/status/{tweet.get('id_str', '')}",
                    source="twitter",
                    subreddit_or_account=f"@{user}",
                    content=text,
                    score=tweet.get("favorite_count", 0),
                    comments=tweet.get("reply_count", 0),
                    published_at=published_at,
                    tags_matched=matched_tags,
                )
                items.append(item)

        except Exception as e:
            logger.error(f"Apify Twitter collection failed: {e}")

        logger.info(f"Twitter (Apify): collected {len(items)} matching tweets")
        return items

    def _collect_nitter(self) -> List[ContentItem]:
        """
        Fallback: Use Nitter RSS feeds (free but unreliable).
        Nitter instances go up and down — you may need to update the base URL.
        """
        import feedparser
        from time import mktime

        items = []
        # Try multiple Nitter instances
        NITTER_INSTANCES = [
            "https://nitter.privacydev.net",
            "https://nitter.poast.org",
            "https://nitter.1d4.us",
        ]

        logger.info(f"Collecting tweets via Nitter RSS for {len(self.accounts)} accounts")

        for account in self.accounts:
            account_clean = account.lstrip("@")
            collected = False

            for instance in NITTER_INSTANCES:
                if collected:
                    break

                rss_url = f"{instance}/{account_clean}/rss"
                try:
                    feed = feedparser.parse(rss_url)
                    if feed.bozo and not feed.entries:
                        continue

                    for entry in feed.entries[:10]:
                        title = entry.get("title", "")
                        desc = entry.get("description", "")
                        link = entry.get("link", "")

                        full_text = f"{title} {desc}"
                        matched_tags = self.matches_topics(full_text)

                        if not matched_tags:
                            continue

                        published_at = None
                        if hasattr(entry, "published_parsed") and entry.published_parsed:
                            try:
                                published_at = datetime.fromtimestamp(
                                    mktime(entry.published_parsed), tz=timezone.utc
                                )
                            except (TypeError, ValueError):
                                pass

                        import re
                        clean_text = re.sub(r"<[^>]+>", "", desc)

                        item = ContentItem(
                            title=clean_text[:120].replace("\n", " ") + "...",
                            url=link.replace(instance, "https://twitter.com"),
                            source="twitter",
                            subreddit_or_account=f"@{account_clean}",
                            content=clean_text[:500],
                            score=0,
                            comments=0,
                            published_at=published_at,
                            tags_matched=matched_tags,
                        )
                        items.append(item)

                    collected = True
                    logger.debug(f"  @{account_clean}: OK via {instance}")

                except Exception as e:
                    logger.debug(f"  @{account_clean}: failed on {instance}: {e}")
                    continue

            if not collected:
                logger.warning(f"  @{account_clean}: all Nitter instances failed")

        logger.info(f"Twitter (Nitter): collected {len(items)} matching tweets")
        return items
