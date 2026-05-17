"""Tests for ArticleWriter — mocks AI API calls."""
import pytest
from unittest.mock import patch, MagicMock

from writing.writer import ArticleWriter
from verification.models import VerificationResult, VerificationStatus


def _make_story():
    story = MagicMock()
    story.id             = 1
    story.title          = "Test Headline for Article"
    story.category       = "technology"
    story.summary        = "Test summary text"
    story.source_name    = "Reuters"
    story.url            = "https://reuters.com/test"
    return story


def _make_verification():
    return VerificationResult(
        story_id=1,
        status=VerificationStatus.VERIFIED,
        source_count=3,
        credibility_score=85,
    )


@patch("writing.writer.generate")
def test_writer_returns_draft(mock_generate):
    mock_generate.return_value = "<p>This is the article content.</p>"
    writer = ArticleWriter()
    draft  = writer.write(_make_story(), _make_verification())
    assert draft.headline    == "Test Headline for Article"
    assert draft.story_id    == 1
    assert draft.category    == "technology"
    assert draft.word_count  > 0
    assert "<p>" in draft.article_html


@patch("writing.writer.generate")
def test_writer_records_model_used(mock_generate):
    mock_generate.return_value = "<p>Article content here.</p>"
    writer = ArticleWriter()
    draft  = writer.write(_make_story(), _make_verification())
    assert draft.ai_model_used != ""


@patch("writing.writer.generate", side_effect=Exception("API error"))
def test_writer_propagates_exception(mock_generate):
    writer = ArticleWriter()
    with pytest.raises(Exception, match="API error"):
        writer.write(_make_story(), _make_verification())
