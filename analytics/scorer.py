"""
Stage 7 — Analytics Feedback Loop.

Reads performance snapshots and adjusts the priority_score of stories
in the discovered_stories table to up-rank content types that perform well
with the audience. This makes the pipeline self-improving over time.
"""
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from core.db.models import AnalyticsSnapshot, PublishedArticle, ArticleDraft, DiscoveredStory
from core.utils.logger import get_logger

logger = get_logger("analytics.scorer")


class FeedbackScorer:
    def __init__(self, session: Session) -> None:
        self.session = session

    def update_priority_scores(self) -> dict:
        """
        Re-score 'new' discovered stories based on historical performance
        of articles in the same category.

        High-performing categories get a +10 priority boost.
        Low-performing categories get a -5 penalty.
        """
        category_scores = self._compute_category_performance()
        if not category_scores:
            logger.info("No analytics data available yet — skipping score update")
            return {"updated": 0}

        avg_score = sum(category_scores.values()) / len(category_scores)
        updated   = 0

        stories = self.session.scalars(
            select(DiscoveredStory).where(DiscoveredStory.status == "new")
        ).all()

        for story in stories:
            cat_score = category_scores.get(story.category)
            if cat_score is None:
                continue
            delta = 10.0 if cat_score > avg_score * 1.2 else (-5.0 if cat_score < avg_score * 0.6 else 0.0)
            if delta:
                story.priority_score = max(0.0, min(100.0, story.priority_score + delta))
                updated += 1

        self.session.commit()
        logger.info(f"Feedback scorer updated priority for {updated} stories")
        return {"updated": updated, "category_scores": category_scores}

    def _compute_category_performance(self) -> dict[str, float]:
        """Average performance_score per category across all analytics snapshots."""
        rows = self.session.execute(
            select(ArticleDraft.category, func.avg(AnalyticsSnapshot.performance_score))
            .join(PublishedArticle, PublishedArticle.draft_id == ArticleDraft.id)
            .join(AnalyticsSnapshot, AnalyticsSnapshot.published_id == PublishedArticle.id)
            .group_by(ArticleDraft.category)
        ).all()
        return {row[0]: float(row[1]) for row in rows if row[1] is not None}

    def get_top_categories(self, n: int = 5) -> list[tuple[str, float]]:
        """Return top N categories by average performance score."""
        scores = self._compute_category_performance()
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:n]
