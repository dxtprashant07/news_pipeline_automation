from sqlalchemy.orm import Session
from sqlalchemy import select, func

from .models import DiscoveredStory
from ..processors.normalizer import NormalizedStory
from ..utils.logger import get_logger

logger = get_logger("storage.repository")


class StoryRepository:
    """
    All database interactions go through here.
    The pipeline never touches SQL directly.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    # ── Write ──────────────────────────────────────────────────────────────

    def save(self, story: NormalizedStory) -> DiscoveredStory | None:
        """Insert a single story. Returns None if it already exists."""
        existing = self.session.scalar(
            select(DiscoveredStory).where(DiscoveredStory.url_hash == story.url_hash)
        )
        if existing:
            return None

        db_story = DiscoveredStory(
            url_hash=story.url_hash,
            content_hash=story.content_hash,
            title=story.title,
            url=story.url,
            clean_url=story.clean_url,
            domain=story.domain,
            summary=story.summary,
            author=story.author,
            image_url=story.image_url,
            source_name=story.source_name,
            category=story.category,
            credibility_score=story.credibility_score,
            priority_score=story.priority_score,
            published_at=story.published_at,
            discovered_at=story.discovered_at,
            extra=story.extra,
            status="new",
        )
        self.session.add(db_story)
        return db_story

    def save_batch(self, stories: list[NormalizedStory]) -> int:
        """Bulk insert. Returns number of new stories saved."""
        saved = 0
        for story in stories:
            try:
                result = self.save(story)
                if result:
                    saved += 1
            except Exception as exc:
                logger.warning(f"Failed to save '{story.title[:60]}': {exc}")
                self.session.rollback()
        self.session.commit()
        logger.info(f"Repository: saved {saved}/{len(stories)} new stories")
        return saved

    # ── Read ───────────────────────────────────────────────────────────────

    def get_existing_url_hashes(self, limit: int = 10_000) -> set[str]:
        """Fetch recent url_hashes for deduplication — doesn't load full rows."""
        rows = self.session.scalars(
            select(DiscoveredStory.url_hash).order_by(
                DiscoveredStory.discovered_at.desc()
            ).limit(limit)
        ).all()
        return set(rows)

    def get_existing_content_hashes(self, limit: int = 10_000) -> set[str]:
        rows = self.session.scalars(
            select(DiscoveredStory.content_hash).order_by(
                DiscoveredStory.discovered_at.desc()
            ).limit(limit)
        ).all()
        return set(rows)

    def fetch_new(
        self,
        limit: int = 50,
        min_credibility: int = 0,
        category: str | None = None,
    ) -> list[DiscoveredStory]:
        """Fetch top-priority unprocessed stories, ready for Phase 2."""
        q = (
            select(DiscoveredStory)
            .where(DiscoveredStory.status == "new")
            .where(DiscoveredStory.credibility_score >= min_credibility)
        )
        if category:
            q = q.where(DiscoveredStory.category == category)
        q = q.order_by(DiscoveredStory.priority_score.desc()).limit(limit)
        return list(self.session.scalars(q).all())

    def get_stats(self) -> dict:
        """Quick summary stats for the dashboard / logs."""
        total = self.session.scalar(select(func.count(DiscoveredStory.id))) or 0
        new   = self.session.scalar(
            select(func.count(DiscoveredStory.id)).where(DiscoveredStory.status == "new")
        ) or 0
        by_category = dict(
            self.session.execute(
                select(DiscoveredStory.category, func.count(DiscoveredStory.id))
                .group_by(DiscoveredStory.category)
            ).all()
        )
        return {"total": total, "new": new, "by_category": by_category}

    # ── Update ─────────────────────────────────────────────────────────────

    def update_status(self, story_id: int, status: str) -> None:
        story = self.session.get(DiscoveredStory, story_id)
        if story:
            story.status = status
            self.session.commit()
