from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class DiscoveredStory(Base):
    __tablename__ = "discovered_stories"

    # Identity
    id           = Column(Integer, primary_key=True, autoincrement=True)
    url_hash     = Column(String(64), unique=True, nullable=False, index=True)
    content_hash = Column(String(64), nullable=False, index=True)

    # Core content
    title        = Column(String(500), nullable=False)
    url          = Column(Text, nullable=False)
    clean_url    = Column(Text)
    domain       = Column(String(200), index=True)
    summary      = Column(Text, default="")
    author       = Column(String(200), default="")
    image_url    = Column(Text, default="")
    source_name  = Column(String(200), nullable=False, index=True)

    # Classification
    category          = Column(String(100), default="general", index=True)
    credibility_score = Column(Integer, default=0)
    priority_score    = Column(Float, default=0.0)

    # Timing
    published_at  = Column(DateTime(timezone=True))
    discovered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Workflow status (for Phase 2/3)
    status = Column(String(50), default="new", index=True)
    # new → fact_checked → written → published → rejected

    # Extra metadata from the source
    extra = Column(JSON, default=dict)

    def __repr__(self) -> str:
        return f"<Story id={self.id} title='{self.title[:50]}' score={self.priority_score}>"
