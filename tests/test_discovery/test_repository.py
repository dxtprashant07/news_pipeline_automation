"""Tests for StoryRepository — uses in-memory SQLite."""
import pytest
from datetime import datetime, timezone

from core.db.models import DiscoveredStory
from core.db.repository import StoryRepository
from discovery.processors.normalizer import NormalizedStory


def _make_normalized_story(url_hash="abc", content_hash="def", title="Test", url="https://reuters.com/a"):
    return NormalizedStory(
        url_hash=url_hash,
        content_hash=content_hash,
        title=title,
        url=url,
        clean_url=url,
        domain="reuters.com",
        summary="Summary text",
        author="",
        image_url="",
        source_name="Reuters",
        published_at=datetime.now(timezone.utc),
        discovered_at=datetime.now(timezone.utc),
        category="technology",
        credibility_score=85,
        priority_score=70.0,
    )


def test_save_new_story(db_session):
    repo  = StoryRepository(db_session)
    story = _make_normalized_story()
    row   = repo.save(story)
    db_session.commit()
    assert row is not None
    assert row.status == "new"


def test_save_duplicate_returns_none(db_session):
    repo  = StoryRepository(db_session)
    story = _make_normalized_story()
    repo.save(story)
    db_session.commit()
    result = repo.save(story)
    assert result is None


def test_fetch_new_stories(db_session):
    repo = StoryRepository(db_session)
    s1   = _make_normalized_story(url_hash="h1", content_hash="c1", url="https://reuters.com/1")
    s2   = _make_normalized_story(url_hash="h2", content_hash="c2", url="https://reuters.com/2")
    repo.save_batch([s1, s2])
    new_stories = repo.fetch_new(limit=10)
    assert len(new_stories) == 2


def test_update_status(db_session):
    repo  = StoryRepository(db_session)
    story = _make_normalized_story()
    row   = repo.save(story)
    db_session.commit()
    repo.update_status(row.id, "fact_checking")
    db_session.refresh(row)
    assert row.status == "fact_checking"


def test_get_stats(db_session):
    repo  = StoryRepository(db_session)
    story = _make_normalized_story()
    repo.save(story)
    db_session.commit()
    stats = repo.get_stats()
    assert stats["total"] == 1
    assert stats["new"] == 1
