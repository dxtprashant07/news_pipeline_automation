from sqlalchemy.orm import Session

from .sources.google_trends import GoogleTrendsSource
from .sources.newsapi import NewsAPISource
from .sources.reddit import RedditSource
from .sources.rss_feeds import RSSFeedSource
from .utils.base import BaseSource, RawStory

from .processors.normalizer import Normalizer, NormalizedStory
from .processors.sanitizer import Sanitizer
from .processors.deduplicator import Deduplicator
from .processors.classifier import Classifier
from .processors.credibility import CredibilityScorer
from .processors.scorer import PriorityScorer

from .storage.repository import StoryRepository
from .config.settings import get_settings
from .utils.logger import get_logger

logger = get_logger("pipeline")


class DiscoveryPipeline:
    """
    Phase 1 pipeline — runs all sources, processes stories,
    and saves to the database in one cohesive flow.

    Each source is isolated: a failure in one never stops the others.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()

        # Sources
        self.sources: list[BaseSource] = [
            GoogleTrendsSource(),
            NewsAPISource(),
            RedditSource(),
            RSSFeedSource(),
        ]

        # Processors
        self.normalizer   = Normalizer()
        self.sanitizer    = Sanitizer()
        self.deduplicator = Deduplicator()
        self.classifier   = Classifier()
        self.cred_scorer  = CredibilityScorer()
        self.prio_scorer  = PriorityScorer()

        # Repository
        self.repo = StoryRepository(session)

    # ── Public entry point ─────────────────────────────────────────────────

    def run(self) -> dict:
        """
        Execute the full pipeline.
        Returns a summary dict with counts for each stage.
        """
        logger.info("=" * 60)
        logger.info("Discovery pipeline started")

        # 1. Fetch from all sources (isolated per source)
        raw_stories = self._fetch_all_sources()

        # 2. Normalize to common schema
        stories = self.normalizer.normalize_all(raw_stories)
        logger.info(f"Normalized: {len(stories)} stories")

        # 3. Sanitize — strip XSS vectors
        stories = self.sanitizer.sanitize_all(stories)

        # 4. Deduplicate against DB + within-batch
        url_hashes     = self.repo.get_existing_url_hashes()
        content_hashes = self.repo.get_existing_content_hashes()
        stories = self.deduplicator.deduplicate(stories, url_hashes, content_hashes)

        # 5. Classify categories
        stories = self.classifier.classify_all(stories)

        # 6. Score credibility
        stories = self.cred_scorer.score_all(stories)

        # 7. Score & rank priority
        stories = self.prio_scorer.score_all(stories)

        # 8. Filter below minimum credibility threshold
        before_filter = len(stories)
        stories = [
            s for s in stories
            if s.credibility_score >= self.settings.min_credibility_score
        ]
        filtered_out = before_filter - len(stories)

        # 9. Cap per-run limit
        stories = stories[: self.settings.max_stories_per_run]

        # 10. Save to database
        saved = self.repo.save_batch(stories)

        # 11. Summary
        stats = self.repo.get_stats()
        summary = {
            "raw_fetched":    len(raw_stories),
            "normalized":     len(stories) + filtered_out,
            "after_dedup":    len(stories) + filtered_out,
            "filtered_out":   filtered_out,
            "saved":          saved,
            "db_total":       stats["total"],
            "db_new":         stats["new"],
            "by_category":    stats["by_category"],
        }

        logger.info(
            f"Pipeline complete — fetched {summary['raw_fetched']}, "
            f"saved {saved} new stories. DB total: {stats['total']}"
        )
        logger.info("=" * 60)
        return summary

    # ── Private helpers ────────────────────────────────────────────────────

    def _fetch_all_sources(self) -> list[RawStory]:
        """
        Run every source inside its own try/except.
        A broken source is logged and skipped — never crashes the run.
        """
        all_raw: list[RawStory] = []

        for source in self.sources:
            try:
                logger.info(f"Fetching from: {source.name}")
                stories = source.fetch()
                logger.info(f"  └─ {source.name}: {len(stories)} stories")
                all_raw.extend(stories)
            except Exception as exc:
                # Per-source isolation — this source is dead but others continue
                logger.error(f"  └─ {source.name}: FAILED with {exc!r} — skipping")

        logger.info(f"Total raw stories fetched: {len(all_raw)}")
        return all_raw
