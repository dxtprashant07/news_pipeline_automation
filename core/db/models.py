from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ── Stage 1+2: Discovery ───────────────────────────────────────────────────

class DiscoveredStory(Base):
    __tablename__ = "discovered_stories"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    url_hash      = Column(String(64), unique=True, nullable=False, index=True)
    content_hash  = Column(String(64), nullable=False, index=True)

    title         = Column(String(500), nullable=False)
    url           = Column(Text, nullable=False)
    clean_url     = Column(Text)
    domain        = Column(String(200), index=True)
    summary       = Column(Text, default="")
    author        = Column(String(200), default="")
    image_url     = Column(Text, default="")
    source_name   = Column(String(200), nullable=False, index=True)

    category          = Column(String(100), default="general", index=True)
    credibility_score = Column(Integer, default=0)
    priority_score    = Column(Float, default=0.0)

    published_at  = Column(DateTime(timezone=True))
    discovered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Workflow status — drives the entire pipeline
    # new → fact_checking → fact_checked → writing → written → published | rejected
    status = Column(String(50), default="new", index=True)

    extra = Column(JSON, default=dict)

    # Relationships
    fact_check  = relationship("FactCheckResult", back_populates="story", uselist=False)
    draft       = relationship("ArticleDraft", back_populates="story", uselist=False)

    def __repr__(self) -> str:
        return f"<Story id={self.id} status={self.status} title='{self.title[:50]}'>"


# ── Stage 3: Fact Verification ─────────────────────────────────────────────

class FactCheckResult(Base):
    __tablename__ = "fact_check_results"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    story_id          = Column(Integer, ForeignKey("discovered_stories.id"), unique=True, nullable=False, index=True)

    status            = Column(String(50), nullable=False, index=True)
    # verified | insufficient_sources | low_credibility | error

    source_count      = Column(Integer, default=0)
    credibility_score = Column(Integer, default=0)
    rejection_reason  = Column(Text, default="")
    search_query_used = Column(Text, default="")
    sources_found     = Column(JSON, default=list)

    checked_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    story = relationship("DiscoveredStory", back_populates="fact_check")


# ── Stage 4: AI Content Generation ────────────────────────────────────────

class ArticleDraft(Base):
    __tablename__ = "article_drafts"

    id       = Column(Integer, primary_key=True, autoincrement=True)
    story_id = Column(Integer, ForeignKey("discovered_stories.id"), unique=True, nullable=False, index=True)

    # Content
    headline     = Column(String(500), nullable=False)
    article_html = Column(Text, nullable=False)
    word_count   = Column(Integer, default=0)
    image_url    = Column(Text, default="")   # DALL-E generated image

    # SEO
    meta_title          = Column(String(100), default="")
    meta_description    = Column(String(200), default="")
    focus_keyword       = Column(String(100), default="")
    secondary_keywords  = Column(JSON, default=list)
    schema_type         = Column(String(50), default="NewsArticle")
    schema_markup       = Column(JSON, default=dict)

    # Metadata
    category      = Column(String(100), default="general", index=True)
    source_url    = Column(Text, default="")
    ai_model_used = Column(String(100), default="")

    # Stage 5 editorial workflow
    # pending_review → approved | rejected
    status       = Column(String(50), default="pending_review", index=True)
    editor_notes = Column(Text, default="")

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    story     = relationship("DiscoveredStory", back_populates="draft")
    published = relationship("PublishedArticle", back_populates="draft", uselist=False)


# ── Stage 6: Publishing ────────────────────────────────────────────────────

class PublishedArticle(Base):
    __tablename__ = "published_articles"

    id       = Column(Integer, primary_key=True, autoincrement=True)
    draft_id = Column(Integer, ForeignKey("article_drafts.id"), unique=True, nullable=False, index=True)

    # WordPress result
    wordpress_post_id  = Column(Integer)
    wordpress_post_url = Column(Text, default="")
    wordpress_status   = Column(String(50), default="")  # publish | draft | failed

    # Social distribution
    buffer_sent        = Column(Boolean, default=False)
    buffer_update_ids  = Column(JSON, default=list)

    # Newsletter
    newsletter_sent    = Column(Boolean, default=False)
    newsletter_campaign_id = Column(String(100), default="")

    published_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    draft = relationship("ArticleDraft", back_populates="published")
    analytics = relationship("AnalyticsSnapshot", back_populates="article")


# ── Stage 7: Analytics ─────────────────────────────────────────────────────

class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    published_id       = Column(Integer, ForeignKey("published_articles.id"), nullable=False, index=True)

    snapshot_date      = Column(DateTime(timezone=True), nullable=False, index=True)

    # GA4 metrics
    page_views         = Column(Integer, default=0)
    sessions           = Column(Integer, default=0)
    avg_time_on_page   = Column(Float, default=0.0)
    bounce_rate        = Column(Float, default=0.0)

    # Search Console metrics
    impressions        = Column(Integer, default=0)
    clicks             = Column(Integer, default=0)
    avg_position       = Column(Float, default=0.0)

    # Derived score — fed back to discovery priority scorer
    performance_score  = Column(Float, default=0.0)

    collected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    article = relationship("PublishedArticle", back_populates="analytics")
