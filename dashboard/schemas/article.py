from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ArticleSummary(BaseModel):
    id: int
    story_id: int
    headline: str
    category: str
    word_count: int
    focus_keyword: str
    credibility_score: int
    seo_score: int = 0
    source_url: str
    status: str
    created_at: datetime
    published_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ArticleDetail(ArticleSummary):
    article_html: str
    meta_title: str
    meta_description: str
    secondary_keywords: list[str]
    schema_markup: dict
    seo_breakdown: dict = {}
    editor_notes: str
    image_url: str


class ApproveRequest(BaseModel):
    editor_notes: Optional[str] = ""


class RejectRequest(BaseModel):
    editor_notes: str


class EditRequest(BaseModel):
    headline: Optional[str] = None
    article_html: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    focus_keyword: Optional[str] = None
    editor_notes: Optional[str] = None


class PipelineStats(BaseModel):
    total_stories: int
    new_stories: int
    fact_checked: int
    written: int
    pending_review: int
    approved: int
    published: int
    total_fact_checks: int
    verified: int
    rejected_checks: int
