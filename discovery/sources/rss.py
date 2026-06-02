import re
import time
from datetime import datetime, timezone

from .base import BaseSource, RawStory
from discovery.config.categories import RSS_FEEDS
from core.utils.rate_limiter import get_limiter
from core.utils.retry import with_retry


def _extract_image(entry) -> str:
    """Pull the best available image URL out of a feedparser entry."""
    # media:thumbnail (most common in news feeds)
    thumbnails = getattr(entry, "media_thumbnail", None) or []
    if thumbnails and isinstance(thumbnails, list):
        url = thumbnails[0].get("url", "")
        if url:
            return url

    # media:content with image mime type
    media = getattr(entry, "media_content", None) or []
    for m in media:
        url = m.get("url", "")
        mime = m.get("type", "")
        if url and ("image" in mime or url.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))):
            return url

    # enclosure (podcast/media feed style)
    for enc in getattr(entry, "enclosures", []) or []:
        url = enc.get("href", "") or enc.get("url", "")
        if url and "image" in enc.get("type", ""):
            return url

    # <img> inside the summary HTML
    summary_html = entry.get("summary") or entry.get("content", [{}])[0].get("value", "")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary_html, re.IGNORECASE)
    if m:
        return m.group(1)

    return ""


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

        for entry in feed.entries[:15]:
            title = (entry.get("title") or "").strip()
            link  = (entry.get("link")  or "").strip()
            if not title or not link:
                continue

            published_at = datetime.now(timezone.utc)
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published_at = datetime.fromtimestamp(
                        time.mktime(entry.published_parsed), tz=timezone.utc
                    )
                except Exception:
                    pass

            summary = entry.get("summary") or entry.get("description") or ""
            summary = re.sub(r"<[^>]+>", "", summary).strip()

            stories.append(RawStory(
                title=title,
                url=link,
                source_name=source_name,
                published_at=published_at,
                summary=summary[:500],
                image_url=_extract_image(entry),
                extra={"feed_url": url, "feed_category": category},
            ))

        return stories
