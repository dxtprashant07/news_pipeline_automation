import requests
from datetime import datetime, timezone
from dateutil import parser as dateparser

from ..utils.base import BaseSource, RawStory
from ..config.settings import get_settings
from ..config.categories import CATEGORIES
from ..utils.rate_limiter import get_limiter
from ..utils.retry import with_retry

NEWSAPI_URL = "https://newsapi.org/v2/top-headlines"


class NewsAPISource(BaseSource):
    name = "newsapi"

    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self.limiter = get_limiter("newsapi")

    def fetch(self) -> list[RawStory]:
        if not self.settings.newsapi_key:
            self.logger.warning("NEWSAPI_KEY not set — skipping NewsAPI source.")
            return []
        try:
            return self._fetch_headlines()
        except Exception as exc:
            self.logger.error(f"NewsAPI fetch failed: {exc}")
            return []

    @with_retry(max_attempts=3, base_delay=2.0, circuit_name="newsapi")
    def _fetch_headlines(self) -> list[RawStory]:
        self.limiter.acquire()

        geo = self.settings.geo_focus
        country = geo.lower() if geo != "GLOBAL" else None

        params: dict = {
            "apiKey": self.settings.newsapi_key,
            "pageSize": 50,
            "language": "en",
        }
        if country:
            params["country"] = country

        resp = requests.get(NEWSAPI_URL, params=params, timeout=15)
        resp.raise_for_status()

        articles = resp.json().get("articles", [])
        stories: list[RawStory] = []

        for art in articles:
            title = (art.get("title") or "").strip()
            url = (art.get("url") or "").strip()
            if not title or not url or title == "[Removed]":
                continue

            pub_raw = art.get("publishedAt")
            try:
                published_at = dateparser.parse(pub_raw) if pub_raw else datetime.now(timezone.utc)
            except Exception:
                published_at = datetime.now(timezone.utc)

            stories.append(RawStory(
                title=title,
                url=url,
                source_name=art.get("source", {}).get("name", self.name),
                published_at=published_at,
                summary=art.get("description") or "",
                author=art.get("author") or "",
                image_url=art.get("urlToImage") or "",
                extra={"content_preview": (art.get("content") or "")[:200]},
            ))

        self.logger.info(f"NewsAPI: fetched {len(stories)} articles")
        return stories
