from datetime import datetime, timezone

from ..utils.base import BaseSource, RawStory
from ..config.categories import RSS_FEEDS
from ..utils.rate_limiter import get_limiter
from ..utils.retry import with_retry


class RSSFeedSource(BaseSource):
    name = "rss"

    def __init__(self) -> None:
        super().__init__()
        self.limiter = get_limiter("rss")

    def fetch(self) -> list[RawStory]:
        try:
            import feedparser
        except ImportError:
            self.logger.error("feedparser not installed. Run: pip install feedparser")
            return []

        stories: list[RawStory] = []
        for feed_cfg in RSS_FEEDS:
            try:
                batch = self._fetch_feed(feed_cfg["url"], feed_cfg.get("category", "general"))
                stories.extend(batch)
            except Exception as exc:
                self.logger.warning(f"RSS feed {feed_cfg['url']} failed: {exc}")
        self.logger.info(f"RSS: fetched {len(stories)} articles across {len(RSS_FEEDS)} feeds")
        return stories

    @with_retry(max_attempts=2, base_delay=1.5, circuit_name="rss")
    def _fetch_feed(self, url: str, category: str) -> list[RawStory]:
        import feedparser
        self.limiter.acquire()

        feed = feedparser.parse(url)
        stories: list[RawStory] = []

        source_name = feed.feed.get("title", url)

        for entry in feed.entries[:15]:  # Cap per feed
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue

            # Parse date
            published_at = datetime.now(timezone.utc)
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    import time
                    published_at = datetime.fromtimestamp(
                        time.mktime(entry.published_parsed), tz=timezone.utc
                    )
                except Exception:
                    pass

            summary = entry.get("summary") or entry.get("description") or ""
            # Strip HTML tags from summary
            import re
            summary = re.sub(r"<[^>]+>", "", summary).strip()

            stories.append(RawStory(
                title=title,
                url=link,
                source_name=source_name,
                published_at=published_at,
                summary=summary[:500],
                image_url="",
                extra={"feed_url": url, "feed_category": category},
            ))

        return stories
