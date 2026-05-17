"""Pipeline stats endpoint — powers the dashboard header metrics."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from dashboard.auth import require_api_key
from dashboard.schemas.article import PipelineStats
from core.db.session import get_session_factory
from core.db.models import DiscoveredStory, ArticleDraft, FactCheckResult, PublishedArticle
from core.config.settings import get_settings
from core.utils.logger import get_logger

logger = get_logger("dashboard.stats")
router = APIRouter(prefix="/stats", tags=["stats"], dependencies=[Depends(require_api_key)])


def get_session():
    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        yield session


@router.get("/", response_model=PipelineStats)
def get_stats(session: Session = Depends(get_session)):
    try:
        def count(model, **filters):
            q = select(func.count(model.id))
            for col, val in filters.items():
                q = q.where(getattr(model, col) == val)
            return session.scalar(q) or 0

        return PipelineStats(
            total_stories=count(DiscoveredStory),
            new_stories=count(DiscoveredStory, status="new"),
            fact_checked=count(DiscoveredStory, status="fact_checked"),
            written=count(DiscoveredStory, status="written"),
            pending_review=count(ArticleDraft, status="pending_review"),
            approved=count(ArticleDraft, status="approved"),
            published=count(PublishedArticle),
            total_fact_checks=count(FactCheckResult),
            verified=count(FactCheckResult, status="verified"),
            rejected_checks=session.scalar(
                select(func.count(FactCheckResult.id))
                .where(FactCheckResult.status != "verified")
            ) or 0,
        )
    except Exception:
        logger.exception("Failed to fetch pipeline stats")
        raise HTTPException(status_code=500, detail="Failed to load stats")
