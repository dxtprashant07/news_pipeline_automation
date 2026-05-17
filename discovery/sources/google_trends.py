import json
import requests
from datetime import datetime, timezone

from .base import BaseSource, RawStory
from core.config.settings import get_settings
from core.utils.rate_limiter import get_limiter
from core.utils.retry import with_retry

# NOTE: Google Trends unofficial API — endpoint may change.
# Current known-working endpoint as of 2026.
TRENDS_URL = "https://trends.google.com/trends/api/dailytrends"


class GoogleTrendsSource(BaseSource):
    name = "google_trends"

    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self.limiter = get_limiter("google_trends")

    def fetch(self) -> list[RawStory]:
        try:
            return self._fetch_trends()
        except Exception as exc:
            self.logger.error(f"GoogleTrends fetch failed: {exc}")
            return []

    @with_retry(max_attempts=3, base_delay=2.0, circuit_name="google_trends")
    def _fetch_trends(self) -> list[RawStory]:
        self.limiter.acquire()

        geo = self.settings.geo_focus if self.settings.geo_focus != "GLOBAL" else "US"

        resp = requests.get(
            TRENDS_URL,
            params={"hl": "en-US", "geo": geo, "ns": 15},
            headers={"User-Agent": "Mozilla/5.0 NewsPipeline/1.0"},
            timeout=15,
        )
        resp.raise_for_status()

        # Google prepends ")]}'\n" to the JSON body — strip it
        raw_json = resp.text[5:]
        data = json.loads(raw_json)

        stories: list[RawStory] = []
        trending_searches = (
            data.get("default", {})
                .get("trendingSearchesDays", [{}])[0]
                .get("trendingSearches", [])
        )

        for item in trending_searches:
            title = item.get("title", {}).get("query", "").strip()
            if not title:
                continue

            articles = item.get("articles", [])
            url      = articles[0].get("url", "")     if articles else ""
            summary  = articles[0].get("snippet", "") if articles else ""
            image    = articles[0].get("image", {}).get("imageUrl", "") if articles else ""

            if not url:
                url = f"https://www.google.com/search?q={title.replace(' ', '+')}"

            stories.append(RawStory(
                title=title,
                url=url,
                source_name=self.name,
                published_at=datetime.now(timezone.utc),
                summary=summary,
                image_url=image,
                extra={"traffic": item.get("formattedTraffic", ""), "geo": geo},
            ))

        self.logger.info(f"GoogleTrends: fetched {len(stories)} trending topics")
        return stories
