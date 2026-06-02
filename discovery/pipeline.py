from sqlalchemy.orm import Session

from .sources.google_trends import GoogleTrendsSource
from .sources.newsapi import NewsAPISource
from .sources.reddit import RedditSource
from .sources.rss import RSSFeedSource
from .sources.twitter import TwitterSource
from .sources.base import BaseSource, RawStory
from .processors.normalizer import Normalizer
from .processors.sanitizer import Sanitizer
from .processors.deduplicator import Deduplicator
from .processors.classifier import Classifier
from .processors.credibility import CredibilityScorer
from .processors.scorer import PriorityScorer
from core.db.repository import StoryRepository
from core.config.settings import get_settings
from core.utils.logger import get_logger

logger = get_logger("discovery.pipeline")


class DiscoveryPipeline:
    """
    Stage 1+2 pipeline — runs all sources, processes stories, saves to DB.

    Each source is isolated: a failure in one never stops the others.
    Flow: fetch → normalize → sanitize → deduplicate → classify → credibility → priority → save
    """

    def __init__(self, session: Session) -> None:
        self.session  = session
        self.settings = get_settings()

        self.sources: list[BaseSource] = [
            GoogleTrendsSource(),
            NewsAPISource(),
            RedditSource(),
            RSSFeedSource(),
            TwitterSource(),
        ]

        self.normalizer   = Normalizer()
        self.sanitizer    = Sanitizer()
        self.deduplicator = Deduplicator()
        self.classifier   = Classifier()
        self.cred_scorer  = CredibilityScorer()
        self.prio_scorer  = PriorityScorer()
        self.repo         = StoryRepository(session)

    def run(self, category: str | None = None, max_stories: int | None = None) -> dict:
        logger.info("=" * 60)
        logger.info(f"Discovery pipeline started — category={category or 'all'}, max={max_stories or self.settings.max_stories_per_run}")

        raw_stories = self._fetch_all_sources()

        stories = self.normalizer.normalize_all(raw_stories)
        logger.info(f"Normalized: {len(stories)} stories")

        stories = self.sanitizer.sanitize_all(stories)

        url_hashes     = self.repo.get_existing_url_hashes()
        content_hashes = self.repo.get_existing_content_hashes()
        stories = self.deduplicator.deduplicate(stories, url_hashes, content_hashes)

        stories = self.classifier.classify_all(stories)
        stories = self.cred_scorer.score_all(stories)
        stories = self.prio_scorer.score_all(stories)

        before_filter = len(stories)
        stories = [s for s in stories if s.credibility_score >= self.settings.min_credibility_score]
        if category:
            stories = [s for s in stories if s.category == category]
        filtered_out = before_filter - len(stories)

        limit = max_stories or self.settings.max_stories_per_run
        stories = stories[:limit]

        saved = self.repo.save_batch(stories)
        stats = self.repo.get_stats()

        summary = {
            "raw_fetched":   len(raw_stories),
            "filtered_out":  filtered_out,
            "saved":         saved,
            "db_total":      stats["total"],
            "db_new":        stats["new"],
            "by_category":   stats["by_category"],
        }

        logger.info(
            f"Discovery complete — fetched {summary['raw_fetched']}, "
            f"saved {saved} new. DB total: {stats['total']}"
        )
        logger.info("=" * 60)
        return summary

    def _fetch_all_sources(self) -> list[RawStory]:
        all_raw: list[RawStory] = []
        for source in self.sources:
            try:
                logger.info(f"Fetching from: {source.name}")
                stories = source.fetch()
                logger.info(f"  └─ {source.name}: {len(stories)} stories")
                all_raw.extend(stories)
            except Exception as exc:
                logger.error(f"  └─ {source.name}: FAILED — {exc!r} — skipping")
        logger.info(f"Total raw stories fetched: {len(all_raw)}")
        return all_raw
