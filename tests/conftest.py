"""
Shared pytest fixtures for all pipeline tests.
Uses an in-memory SQLite database — no disk I/O, no state leakage between tests.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.db.models import Base


@pytest.fixture(scope="function")
def db_session():
    """In-memory SQLite session — created fresh for each test function."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionFactory() as session:
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture
def sample_story_data():
    """Minimal data dict to build a DiscoveredStory for tests."""
    return {
        "url_hash":         "abc123",
        "content_hash":     "def456",
        "title":            "Test Story Headline",
        "url":              "https://reuters.com/test-story",
        "clean_url":        "https://reuters.com/test-story",
        "domain":           "reuters.com",
        "summary":          "This is a test story summary for unit testing.",
        "author":           "Test Author",
        "image_url":        "",
        "source_name":      "Reuters",
        "category":         "technology",
        "credibility_score": 90,
        "priority_score":    80.0,
        "status":           "new",
        "extra":            {},
    }
