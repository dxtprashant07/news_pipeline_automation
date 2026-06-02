"""
Stage 5 — Editor Review Dashboard routes.

GET  /articles/           → list pending_review drafts
GET  /articles/{id}       → get one article with full HTML
POST /articles/{id}/approve → approve (moves to publisher queue)
POST /articles/{id}/reject  → reject with reason
PATCH /articles/{id}        → inline edit (headline, HTML, SEO fields)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dashboard.auth import require_api_key
from dashboard.schemas.article import (
    ArticleSummary, ArticleDetail, ApproveRequest, RejectRequest, EditRequest
)
from core.db.session import get_session_factory
from core.db.repository import DraftRepository
from core.db.models import ArticleDraft, FactCheckResult, DiscoveredStory
from core.config.settings import get_settings
from core.utils.logger import get_logger

logger = get_logger("dashboard.articles")
router = APIRouter(prefix="/articles", tags=["articles"], dependencies=[Depends(require_api_key)])


def get_session():
    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        yield session


@router.get("/", response_model=list[ArticleSummary])
def list_pending(limit: int = 50, session: Session = Depends(get_session)):
    """List all drafts waiting for editor review, ordered oldest first."""
    try:
        repo = DraftRepository(session)
        drafts = repo.get_pending_review(limit=limit)
        results = []
        for draft in drafts:
            fact_check = session.query(FactCheckResult).filter_by(story_id=draft.story_id).first()
            credibility = fact_check.credibility_score if fact_check else 0
            story = session.get(DiscoveredStory, draft.story_id)
            results.append(ArticleSummary(
                id=draft.id,
                story_id=draft.story_id,
                headline=draft.headline,
                category=draft.category,
                word_count=draft.word_count,
                focus_keyword=draft.focus_keyword,
                credibility_score=credibility,
                seo_score=draft.seo_score or 0,
                source_url=draft.source_url,
                status=draft.status,
                created_at=draft.created_at,
                published_at=story.published_at if story else None,
            ))
        return results
    except Exception:
        logger.exception("Failed to list pending articles")
        raise HTTPException(status_code=500, detail="Failed to load articles")


@router.get("/{draft_id}", response_model=ArticleDetail)
def get_article(draft_id: int, session: Session = Depends(get_session)):
    """Get full article detail including HTML, SEO fields, and source info."""
    try:
        draft = session.get(ArticleDraft, draft_id)
        if not draft:
            raise HTTPException(status_code=404, detail="Article not found")

        fact_check = session.query(FactCheckResult).filter_by(story_id=draft.story_id).first()
        credibility = fact_check.credibility_score if fact_check else 0
        story = session.get(DiscoveredStory, draft.story_id)

        return ArticleDetail(
            id=draft.id,
            story_id=draft.story_id,
            headline=draft.headline,
            article_html=draft.article_html,
            category=draft.category,
            word_count=draft.word_count,
            focus_keyword=draft.focus_keyword,
            meta_title=draft.meta_title,
            meta_description=draft.meta_description,
            secondary_keywords=draft.secondary_keywords or [],
            schema_markup=draft.schema_markup or {},
            credibility_score=credibility,
            seo_score=draft.seo_score or 0,
            seo_breakdown=draft.seo_breakdown or {},
            source_url=draft.source_url,
            image_url=draft.image_url or "",
            editor_notes=draft.editor_notes or "",
            status=draft.status,
            created_at=draft.created_at,
            published_at=story.published_at if story else None,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Failed to load article {draft_id}")
        raise HTTPException(status_code=500, detail="Failed to load article")


@router.post("/{draft_id}/approve")
def approve_article(draft_id: int, body: ApproveRequest, session: Session = Depends(get_session)):
    """Approve a draft — moves it to the publisher queue."""
    try:
        repo = DraftRepository(session)
        draft = repo.update_draft_status(draft_id, "approved", body.editor_notes or "")
        if not draft:
            raise HTTPException(status_code=404, detail="Article not found")
        return {"status": "approved", "draft_id": draft_id}
    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Failed to approve article {draft_id}")
        raise HTTPException(status_code=500, detail="Failed to approve article")


@router.post("/{draft_id}/reject")
def reject_article(draft_id: int, body: RejectRequest, session: Session = Depends(get_session)):
    """Reject a draft with an editor reason."""
    try:
        repo = DraftRepository(session)
        draft = repo.update_draft_status(draft_id, "rejected", body.editor_notes)
        if not draft:
            raise HTTPException(status_code=404, detail="Article not found")
        return {"status": "rejected", "draft_id": draft_id}
    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Failed to reject article {draft_id}")
        raise HTTPException(status_code=500, detail="Failed to reject article")


@router.patch("/{draft_id}")
def edit_article(draft_id: int, body: EditRequest, session: Session = Depends(get_session)):
    """Inline-edit any article field before approving."""
    from datetime import datetime, timezone
    try:
        draft = session.get(ArticleDraft, draft_id)
        if not draft:
            raise HTTPException(status_code=404, detail="Article not found")

        if body.headline is not None:
            draft.headline = body.headline
        if body.article_html is not None:
            draft.article_html = body.article_html
        if body.meta_title is not None:
            draft.meta_title = body.meta_title
        if body.meta_description is not None:
            draft.meta_description = body.meta_description
        if body.focus_keyword is not None:
            draft.focus_keyword = body.focus_keyword
        if body.editor_notes is not None:
            draft.editor_notes = body.editor_notes

        draft.updated_at = datetime.now(timezone.utc)
        session.commit()
        return {"status": "updated", "draft_id": draft_id}
    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Failed to edit article {draft_id}")
        raise HTTPException(status_code=500, detail="Failed to update article")
