from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from .models import (
    DiscoveredStory, FactCheckResult, ArticleDraft, PublishedArticle
)
from ..utils.logger import get_logger

logger = get_logger("db.repository")


class StoryRepository:
    """Read/write access to discovered_stories. Used by discovery and verification pipelines."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, story) -> DiscoveredStory | None:
        existing = self.session.scalar(
            select(DiscoveredStory).where(DiscoveredStory.url_hash == story.url_hash)
        )
        if existing:
            return None
        row = DiscoveredStory(
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
        self.session.add(row)
        return row

    def save_batch(self, stories: list) -> int:
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
        logger.info(f"Saved {saved}/{len(stories)} new stories")
        return saved

    def get_existing_url_hashes(self, limit: int = 10_000) -> set[str]:
        rows = self.session.scalars(
            select(DiscoveredStory.url_hash)
            .order_by(DiscoveredStory.discovered_at.desc())
            .limit(limit)
        ).all()
        return set(rows)

    def get_existing_content_hashes(self, limit: int = 10_000) -> set[str]:
        rows = self.session.scalars(
            select(DiscoveredStory.content_hash)
            .order_by(DiscoveredStory.discovered_at.desc())
            .limit(limit)
        ).all()
        return set(rows)

    def fetch_new(self, limit: int = 50, min_credibility: int = 0, category: str | None = None) -> list[DiscoveredStory]:
        q = (
            select(DiscoveredStory)
            .where(DiscoveredStory.status == "new")
            .where(DiscoveredStory.credibility_score >= min_credibility)
        )
        if category:
            q = q.where(DiscoveredStory.category == category)
        q = q.order_by(DiscoveredStory.priority_score.desc()).limit(limit)
        return list(self.session.scalars(q).all())

    def fetch_fact_checked(self, limit: int = 50, min_credibility: int = 0) -> list[DiscoveredStory]:
        q = (
            select(DiscoveredStory)
            .where(DiscoveredStory.status == "fact_checked")
            .where(DiscoveredStory.credibility_score >= min_credibility)
            .order_by(DiscoveredStory.priority_score.desc())
            .limit(limit)
        )
        return list(self.session.scalars(q).all())

    def update_status(self, story_id: int, status: str) -> None:
        story = self.session.get(DiscoveredStory, story_id)
        if story:
            story.status = status
            self.session.commit()

    def get_stats(self) -> dict:
        total = self.session.scalar(select(func.count(DiscoveredStory.id))) or 0
        new = self.session.scalar(
            select(func.count(DiscoveredStory.id)).where(DiscoveredStory.status == "new")
        ) or 0
        by_status = dict(
            self.session.execute(
                select(DiscoveredStory.status, func.count(DiscoveredStory.id))
                .group_by(DiscoveredStory.status)
            ).all()
        )
        by_category = dict(
            self.session.execute(
                select(DiscoveredStory.category, func.count(DiscoveredStory.id))
                .group_by(DiscoveredStory.category)
            ).all()
        )
        return {"total": total, "new": new, "by_status": by_status, "by_category": by_category}


class DraftRepository:
    """Read/write access to fact_check_results and article_drafts. Used by verification and writing pipelines."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save_fact_check(self, result) -> FactCheckResult:
        existing = self.session.scalar(
            select(FactCheckResult).where(FactCheckResult.story_id == result.story_id)
        )
        row = existing or FactCheckResult(story_id=result.story_id)
        if not existing:
            self.session.add(row)

        row.status             = result.status.value
        row.source_count       = result.source_count
        row.credibility_score  = result.credibility_score
        row.rejection_reason   = result.rejection_reason
        row.search_query_used  = result.search_query_used
        row.sources_found      = [
            {"url": s.url, "domain": s.domain, "title": s.title, "tier": s.credibility_tier}
            for s in result.sources_found
        ]
        row.checked_at = datetime.now(timezone.utc)
        self.session.commit()
        return row

    def save_draft(self, draft) -> ArticleDraft:
        existing = self.session.scalar(
            select(ArticleDraft).where(ArticleDraft.story_id == draft.story_id)
        )
        row = existing or ArticleDraft(story_id=draft.story_id)
        if not existing:
            self.session.add(row)

        row.headline           = draft.headline
        row.article_html       = draft.article_html
        row.word_count         = draft.word_count
        row.image_url          = getattr(draft, "image_url", "")
        row.meta_title         = draft.seo.meta_title
        row.meta_description   = draft.seo.meta_description
        row.focus_keyword      = draft.seo.focus_keyword
        row.secondary_keywords = draft.seo.secondary_keywords
        row.schema_type        = draft.seo.schema_type
        row.schema_markup      = draft.seo.schema_markup
        row.category           = draft.category
        row.source_url         = draft.source_url
        row.ai_model_used      = draft.ai_model_used
        row.status             = "pending_review"
        row.updated_at         = datetime.now(timezone.utc)
        self.session.commit()
        return row

    def get_pending_review(self, limit: int = 50) -> list[ArticleDraft]:
        return list(
            self.session.scalars(
                select(ArticleDraft)
                .where(ArticleDraft.status == "pending_review")
                .order_by(ArticleDraft.created_at.asc())
                .limit(limit)
            ).all()
        )

    def get_approved(self, limit: int = 50) -> list[ArticleDraft]:
        return list(
            self.session.scalars(
                select(ArticleDraft)
                .where(ArticleDraft.status == "approved")
                .order_by(ArticleDraft.updated_at.asc())
                .limit(limit)
            ).all()
        )

    def update_draft_status(self, draft_id: int, status: str, editor_notes: str = "") -> ArticleDraft | None:
        draft = self.session.get(ArticleDraft, draft_id)
        if draft:
            draft.status       = status
            draft.editor_notes = editor_notes
            draft.updated_at   = datetime.now(timezone.utc)
            self.session.commit()
        return draft

    def get_rejection_log(self, limit: int = 100) -> list[FactCheckResult]:
        return list(
            self.session.scalars(
                select(FactCheckResult)
                .where(FactCheckResult.status != "verified")
                .order_by(FactCheckResult.checked_at.desc())
                .limit(limit)
            ).all()
        )

    def get_stats(self) -> dict:
        total_checks = self.session.scalar(select(func.count(FactCheckResult.id))) or 0
        verified     = self.session.scalar(
            select(func.count(FactCheckResult.id)).where(FactCheckResult.status == "verified")
        ) or 0
        total_drafts = self.session.scalar(select(func.count(ArticleDraft.id))) or 0
        pending      = self.session.scalar(
            select(func.count(ArticleDraft.id)).where(ArticleDraft.status == "pending_review")
        ) or 0
        approved     = self.session.scalar(
            select(func.count(ArticleDraft.id)).where(ArticleDraft.status == "approved")
        ) or 0

        return {
            "total_fact_checks": total_checks,
            "verified":          verified,
            "rejected":          total_checks - verified,
            "total_drafts":      total_drafts,
            "pending_review":    pending,
            "approved":          approved,
        }


class PublisherRepository:
    """Read/write access to published_articles. Used by the publisher pipeline."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save_published(self, draft_id: int, wp_post_id: int, wp_url: str) -> PublishedArticle:
        row = PublishedArticle(
            draft_id=draft_id,
            wordpress_post_id=wp_post_id,
            wordpress_post_url=wp_url,
            wordpress_status="publish",
        )
        self.session.add(row)
        self.session.commit()
        return row

    def get_unpublished_approved(self, limit: int = 20) -> list[ArticleDraft]:
        """Approved drafts that haven't been pushed to WordPress yet."""
        published_draft_ids = self.session.scalars(
            select(PublishedArticle.draft_id)
        ).all()
        return list(
            self.session.scalars(
                select(ArticleDraft)
                .where(ArticleDraft.status == "approved")
                .where(ArticleDraft.id.notin_(published_draft_ids))
                .order_by(ArticleDraft.updated_at.asc())
                .limit(limit)
            ).all()
        )
