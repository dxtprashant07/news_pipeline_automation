from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SEOMetadata:
    meta_title: str = ""
    meta_description: str = ""
    focus_keyword: str = ""
    secondary_keywords: list[str] = field(default_factory=list)
    schema_type: str = "NewsArticle"
    schema_markup: dict = field(default_factory=dict)


@dataclass
class ArticleDraft:
    """
    Complete generated article ready for the Stage 5 editor dashboard.
    story_id links back to discovered_stories.
    """
    story_id: int
    headline: str
    article_html: str
    word_count: int
    seo: SEOMetadata
    category: str
    source_url: str
    ai_model_used: str
    image_url: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
