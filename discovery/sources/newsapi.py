import requests
from datetime import datetime, timezone
from dateutil import parser as dateparser

from .base import BaseSource, RawStory
from core.config.settings import get_settings
from core.utils.rate_limiter import get_limiter
from core.utils.retry import with_retry

HEADLINES_URL  = "https://newsapi.org/v2/top-headlines"
EVERYTHING_URL = "https://newsapi.org/v2/everything"

# Known Indian news source IDs accepted by NewsAPI
_INDIA_SOURCES = "the-times-of-india,ndtv,the-hindu,the-indian-express,google-news-in"

# Fallback keyword query when country-filtered headlines return nothing
_INDIA_QUERY = (
    "india OR modi OR delhi OR mumbai OR sensex OR "
    "bollywood OR ipl OR bcci OR rupee OR rbi"
)


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
            stories = self._fetch_top_headlines()
            if not stories:
                self.logger.info("Top-headlines returned 0 — trying /everything fallback")
                stories = self._fetch_everything_fallback()
            return stories
        except Exception as exc:
            self.logger.error(f"NewsAPI fetch failed: {exc}")
            return []

    @with_retry(max_attempts=2, base_delay=2.0, circuit_name="newsapi")
    def _fetch_top_headlines(self) -> list[RawStory]:
        self.limiter.acquire()

        geo     = self.settings.geo_focus
        country = geo.lower() if geo != "GLOBAL" else None

        params: dict = {
            "apiKey":   self.settings.newsapi_key,
            "pageSize": 50,
            "language": "en",
        }
        if country:
            params["country"] = country

        resp = requests.get(HEADLINES_URL, params=params, timeout=15)

        # Check for API-level errors before raise_for_status
        if resp.status_code != 200:
            data = resp.json()
            self.logger.warning(
                f"NewsAPI top-headlines error {resp.status_code}: "
                f"{data.get('code')} — {data.get('message')}"
            )
            resp.raise_for_status()

        data = resp.json()
        if data.get("status") == "error":
            self.logger.warning(
                f"NewsAPI returned error: {data.get('code')} — {data.get('message')}"
            )
            return []

        return self._parse_articles(data.get("articles", []))

    @with_retry(max_attempts=2, base_delay=2.0, circuit_name="newsapi")
    def _fetch_everything_fallback(self) -> list[RawStory]:
        """
        /v2/everything is more permissive on the free plan than /v2/top-headlines
        with a country filter.  Uses Indian source IDs first, then keyword query.
        """
        self.limiter.acquire()

        geo = self.settings.geo_focus

        # Try source-based query for IN, fall back to keyword query for others
        if geo == "IN":
            params: dict = {
                "apiKey":   self.settings.newsapi_key,
                "sources":  _INDIA_SOURCES,
                "pageSize": 50,
                "language": "en",
                "sortBy":   "publishedAt",
            }
        else:
            params = {
                "apiKey":   self.settings.newsapi_key,
                "q":        "breaking news",
                "pageSize": 50,
                "language": "en",
                "sortBy":   "publishedAt",
            }

        resp = requests.get(EVERYTHING_URL, params=params, timeout=15)

        if resp.status_code != 200:
            data = resp.json()
            self.logger.warning(
                f"NewsAPI /everything error {resp.status_code}: "
                f"{data.get('code')} — {data.get('message')}"
            )
            # If sources query fails (some plans don't allow it), retry with keywords
            if geo == "IN" and data.get("code") == "sourcesAndCountryAndLanguageExclusive":
                return self._fetch_everything_keyword()
            resp.raise_for_status()

        data = resp.json()
        if data.get("status") == "error":
            self.logger.warning(
                f"NewsAPI /everything error: {data.get('code')} — {data.get('message')}"
            )
            if geo == "IN":
                return self._fetch_everything_keyword()
            return []

        stories = self._parse_articles(data.get("articles", []))
        self.logger.info(f"NewsAPI /everything: fetched {len(stories)} articles")
        return stories

    def _fetch_everything_keyword(self) -> list[RawStory]:
        """Last-resort fallback: keyword query, works on all plan tiers."""
        self.limiter.acquire()

        params = {
            "apiKey":   self.settings.newsapi_key,
            "q":        _INDIA_QUERY,
            "pageSize": 50,
            "language": "en",
            "sortBy":   "publishedAt",
        }

        try:
            resp = requests.get(EVERYTHING_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "error":
                self.logger.warning(
                    f"NewsAPI keyword fallback error: {data.get('code')} — {data.get('message')}"
                )
                return []
            stories = self._parse_articles(data.get("articles", []))
            self.logger.info(f"NewsAPI keyword fallback: fetched {len(stories)} articles")
            return stories
        except Exception as exc:
            self.logger.error(f"NewsAPI keyword fallback failed: {exc}")
            return []

    def _parse_articles(self, articles: list) -> list[RawStory]:
        stories: list[RawStory] = []
        for art in articles:
            title = (art.get("title") or "").strip()
            url   = (art.get("url")   or "").strip()
            if not title or not url or title == "[Removed]" or url == "https://removed.com":
                continue

            pub_raw = art.get("publishedAt")
            try:
                published_at = dateparser.parse(pub_raw) if pub_raw else datetime.now(timezone.utc)
            except Exception:
                published_at = datetime.now(timezone.utc)

            source_name = art.get("source", {}).get("name") or self.name

            stories.append(RawStory(
                title=title,
                url=url,
                source_name=source_name,
                published_at=published_at,
                summary=art.get("description") or "",
                author=art.get("author") or "",
                image_url=art.get("urlToImage") or "",
                extra={"content_preview": (art.get("content") or "")[:200]},
            ))

        self.logger.info(f"NewsAPI: fetched {len(stories)} articles")
        return stories
