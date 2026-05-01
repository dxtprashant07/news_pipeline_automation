"""
Tests for the storage layer.
Uses an in-memory SQLite database — no file created.
Run with: pytest tests/test_storage.py -v
"""
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from storage.models import Base, DiscoveredStory
from storage.repository import StoryRepository
from processors.normalizer import NormalizedStory


@pytest.fixture
def session():
    """Fresh in-memory SQLite DB for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as s:
        yield s


def make_normalized(suffix: str = "1") -> NormalizedStory:
    return NormalizedStory(
        url_hash=f"hash_{suffix}",
        content_hash=f"content_{suffix}",
        title=f"Test Story {suffix}",
        url=f"https://example.com/story-{suffix}",
        clean_url=f"https://example.com/story-{suffix}",
        domain="example.com",
        summary="Test summary.",
        author="Author",
        image_url="https://example.com/img.jpg",
        source_name="TestSource",
        published_at=datetime.now(timezone.utc),
        discovered_at=datetime.now(timezone.utc),
        category="technology",
        credibility_score=75,
        priority_score=65.0,
        extra={},
    )


class TestStoryRepository:
    def test_save_new_story(self, session):
        repo = StoryRepository(session)
        story = make_normalized("1")
        result = repo.save(story)
        assert result is not None
        assert result.title == "Test Story 1"

    def test_save_duplicate_returns_none(self, session):
        repo = StoryRepository(session)
        story = make_normalized("1")
        repo.save(story)
        session.commit()
        result = repo.save(story)
        assert result is None

    def test_save_batch_returns_count(self, session):
        repo = StoryRepository(session)
        stories = [make_normalized(str(i)) for i in range(5)]
        count = repo.save_batch(stories)
        assert count == 5

    def test_save_batch_skips_duplicates(self, session):
        repo = StoryRepository(session)
        stories = [make_normalized("1"), make_normalized("1")]
        count = repo.save_batch(stories)
        assert count == 1

    def test_get_existing_url_hashes(self, session):
        repo = StoryRepository(session)
        repo.save_batch([make_normalized("a"), make_normalized("b")])
        hashes = repo.get_existing_url_hashes()
        assert "hash_a" in hashes
        assert "hash_b" in hashes

    def test_fetch_new_returns_status_new(self, session):
        repo = StoryRepository(session)
        repo.save_batch([make_normalized("1"), make_normalized("2")])
        results = repo.fetch_new(limit=10)
        assert len(results) == 2
        assert all(r.status == "new" for r in results)

    def test_fetch_new_filters_by_credibility(self, session):
        repo = StoryRepository(session)
        low = make_normalized("low")
        low.credibility_score = 20
        high = make_normalized("high")
        high.credibility_score = 80
        repo.save_batch([low, high])
        results = repo.fetch_new(min_credibility=50)
        assert len(results) == 1
        assert results[0].credibility_score == 80

    def test_update_status(self, session):
        repo = StoryRepository(session)
        repo.save(make_normalized("1"))
        session.commit()
        story = session.query(DiscoveredStory).first()
        repo.update_status(story.id, "published")
        updated = session.get(DiscoveredStory, story.id)
        assert updated.status == "published"

    def test_get_stats(self, session):
        repo = StoryRepository(session)
        repo.save_batch([make_normalized("1"), make_normalized("2")])
        stats = repo.get_stats()
        assert stats["total"] == 2
        assert stats["new"] == 2
        assert "technology" in stats["by_category"]
