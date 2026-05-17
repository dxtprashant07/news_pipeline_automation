"""Tests for discovery processors — no external calls."""
import pytest
from datetime import datetime, timezone

from discovery.sources.base import RawStory
from discovery.processors.normalizer import Normalizer, NormalizedStory
from discovery.processors.sanitizer import Sanitizer
from discovery.processors.deduplicator import Deduplicator
from discovery.processors.classifier import Classifier
from discovery.processors.credibility import CredibilityScorer
from discovery.processors.scorer import PriorityScorer


def _make_raw(title="Test Headline", url="https://reuters.com/test", source="Reuters"):
    return RawStory(
        title=title,
        url=url,
        source_name=source,
        published_at=datetime.now(timezone.utc),
        summary="Test summary for the story.",
    )


def _make_normalized(**kwargs):
    base = dict(
        url_hash="abc123", content_hash="def456",
        title="Test Headline", url="https://reuters.com/test",
        clean_url="https://reuters.com/test", domain="reuters.com",
        summary="Test summary", author="", image_url="",
        source_name="Reuters",
        published_at=datetime.now(timezone.utc),
        discovered_at=datetime.now(timezone.utc),
    )
    base.update(kwargs)
    return NormalizedStory(**base)


class TestNormalizer:
    def test_normalize_valid_story(self):
        raw = _make_raw()
        story = Normalizer().normalize(raw)
        assert story is not None
        assert story.title == "Test Headline"
        assert story.domain == "reuters.com"

    def test_normalize_drops_missing_title(self):
        raw = _make_raw(title="")
        assert Normalizer().normalize(raw) is None

    def test_normalize_drops_missing_url(self):
        raw = _make_raw(url="")
        assert Normalizer().normalize(raw) is None

    def test_normalize_strips_tracking_params(self):
        raw = _make_raw(url="https://reuters.com/test?utm_source=google&utm_medium=cpc")
        story = Normalizer().normalize(raw)
        assert "utm_source" not in story.clean_url


class TestSanitizer:
    def test_strips_script_tags(self):
        story = _make_normalized(title="Hello <script>alert('xss')</script> World")
        result = Sanitizer().sanitize(story)
        assert "<script>" not in result.title
        assert "alert" not in result.title

    def test_strips_javascript_url(self):
        story = _make_normalized(image_url="javascript:alert(1)")
        result = Sanitizer().sanitize(story)
        assert result.image_url == ""

    def test_safe_url_passes_through(self):
        url = "https://cdn.reuters.com/image.jpg"
        story = _make_normalized(image_url=url)
        result = Sanitizer().sanitize(story)
        assert result.image_url == url


class TestDeduplicator:
    def test_removes_url_duplicates(self):
        stories = [_make_normalized(url_hash="same"), _make_normalized(url_hash="same")]
        result = Deduplicator().deduplicate(stories)
        assert len(result) == 1

    def test_removes_content_duplicates(self):
        stories = [
            _make_normalized(url_hash="a1", content_hash="same"),
            _make_normalized(url_hash="a2", content_hash="same"),
        ]
        result = Deduplicator().deduplicate(stories)
        assert len(result) == 1

    def test_removes_against_existing_hashes(self):
        stories = [_make_normalized(url_hash="existing")]
        result = Deduplicator().deduplicate(stories, existing_url_hashes={"existing"})
        assert len(result) == 0


class TestClassifier:
    def test_classifies_tech_story(self):
        story = _make_normalized(title="New AI chip released by startup", summary="machine learning breakthrough")
        Classifier().classify(story)
        assert story.category == "technology"

    def test_fallback_to_general(self):
        story = _make_normalized(title="Something completely unrelated zxqw")
        Classifier().classify(story)
        assert story.category == "general"


class TestCredibilityScorer:
    def test_tier1_domain_gets_high_score(self):
        story = _make_normalized(domain="reuters.com", source_name="rss")
        CredibilityScorer().score(story)
        assert story.credibility_score >= 80

    def test_unknown_domain_gets_mid_score(self):
        story = _make_normalized(domain="unknownblog.xyz", source_name="rss")
        CredibilityScorer().score(story)
        assert 40 <= story.credibility_score <= 65


class TestPriorityScorer:
    def test_scores_are_between_0_and_100(self):
        story = _make_normalized(domain="reuters.com")
        story.credibility_score = 90
        PriorityScorer().score(story)
        assert 0.0 <= story.priority_score <= 100.0

    def test_sorts_by_priority(self):
        low  = _make_normalized(url_hash="low",  content_hash="l")
        high = _make_normalized(url_hash="high", content_hash="h")
        low.credibility_score  = 10
        high.credibility_score = 90
        result = PriorityScorer().score_all([low, high])
        assert result[0].credibility_score == 90
