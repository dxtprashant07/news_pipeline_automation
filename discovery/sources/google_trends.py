from datetime import datetime, timezone

from .base import BaseSource, RawStory
from core.config.settings import get_settings
from core.utils.rate_limiter import get_limiter
from core.utils.logger import get_logger

logger = get_logger("sources.google_trends")

# Country code → pytrends pn (property name) mapping
_GEO_TO_PN = {
    "IN": "india",
    "US": "united_states",
    "GB": "united_kingdom",
    "GLOBAL": "united_states",
}


class GoogleTrendsSource(BaseSource):
    name = "google_trends"

    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self.limiter = get_limiter("google_trends")

    def fetch(self) -> list[RawStory]:
        try:
            from pytrends.request import TrendReq
        except ImportError:
            self.logger.error("pytrends not installed. Run: pip install pytrends")
            return []

        try:
            return self._fetch_with_pytrends(TrendReq)
        except Exception as exc:
            self.logger.error(f"GoogleTrends fetch failed: {exc}")
            return []

    def _fetch_with_pytrends(self, TrendReq) -> list[RawStory]:
        self.limiter.acquire()

        geo = self.settings.geo_focus.upper()
        pn  = _GEO_TO_PN.get(geo, "india")

        pt = TrendReq(hl="en-US", tz=330, timeout=(10, 30), retries=2, backoff_factor=0.5)

        # trending_searches returns a DataFrame; column 0 holds the trend strings
        df = pt.trending_searches(pn=pn)
        trends = df[0].dropna().tolist()[:25]

        stories: list[RawStory] = []
        for trend in trends:
            trend = str(trend).strip()
            if not trend:
                continue
            stories.append(RawStory(
                title=trend,
                url=f"https://www.google.com/search?q={trend.replace(' ', '+')}+news",
                source_name=self.name,
                published_at=datetime.now(timezone.utc),
                summary=f"Trending search: {trend}",
                extra={"geo": geo, "pn": pn},
            ))

        self.logger.info(f"GoogleTrends: fetched {len(stories)} trending topics for {geo}")
        return stories
