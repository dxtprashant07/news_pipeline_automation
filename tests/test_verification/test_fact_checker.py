"""Tests for the fact-checker — mocks Bing API calls."""
import pytest
from unittest.mock import patch, MagicMock

from verification.fact_checker import FactChecker
from verification.models import VerificationStatus


def _make_story(id=1, title="Test Story", url="https://reuters.com/test",
                credibility_score=85):
    story = MagicMock()
    story.id               = id
    story.title            = title
    story.url              = url
    story.credibility_score = credibility_score
    return story


class TestFactCheckerFallback:
    """Tests for the no-API-key fallback mode."""

    def test_high_credibility_story_passes(self, monkeypatch):
        monkeypatch.setenv("BING_SEARCH_API_KEY", "")
        monkeypatch.setenv("CREDIBILITY_THRESHOLD", "75")
        checker = FactChecker()
        story   = _make_story(credibility_score=90)
        result  = checker.check(story)
        assert result.status == VerificationStatus.VERIFIED

    def test_low_credibility_story_rejected(self, monkeypatch):
        monkeypatch.setenv("BING_SEARCH_API_KEY", "")
        monkeypatch.setenv("CREDIBILITY_THRESHOLD", "75")
        checker = FactChecker()
        story   = _make_story(credibility_score=40)
        result  = checker.check(story)
        assert result.status == VerificationStatus.LOW_CREDIBILITY
        assert result.rejection_reason != ""

    def test_error_is_captured_not_raised(self):
        checker = FactChecker()
        story   = MagicMock(side_effect=Exception("boom"))
        story.id = 99
        # Should return ERROR status, not raise
        result = checker.check(story)
        assert result.status == VerificationStatus.ERROR


class TestFactCheckerBing:
    """Tests for the Bing search strategy."""

    @patch("verification.fact_checker.requests.get")
    def test_sufficient_sources_passes(self, mock_get, monkeypatch):
        monkeypatch.setenv("BING_SEARCH_API_KEY", "fake-key")

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "webPages": {
                "value": [
                    {"url": "https://reuters.com/story",  "name": "Reuters"},
                    {"url": "https://apnews.com/story",   "name": "AP News"},
                    {"url": "https://bbc.com/story",      "name": "BBC"},
                ]
            }
        }
        mock_get.return_value = mock_resp

        checker = FactChecker()
        story   = _make_story(credibility_score=80)
        result  = checker.check(story)
        assert result.status == VerificationStatus.VERIFIED
        assert result.source_count >= 3

    @patch("verification.fact_checker.requests.get")
    def test_insufficient_sources_fails(self, mock_get, monkeypatch):
        monkeypatch.setenv("BING_SEARCH_API_KEY", "fake-key")

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"webPages": {"value": []}}
        mock_get.return_value = mock_resp

        checker = FactChecker()
        story   = _make_story(credibility_score=80)
        result  = checker.check(story)
        assert result.status == VerificationStatus.INSUFFICIENT_SOURCES
