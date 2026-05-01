"""
Tests for all source modules.
Run with: pytest tests/test_sources.py -v
"""
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from sources.base import RawStory, BaseSource
from sources.newsapi import NewsAPISource
from sources.reddit import RedditSource
from sources.rss_feeds import RSSFeedSource


# ── Base ──────────────────────────────────────────────────────────────────

def test_raw_story_defaults():
    story = RawStory(title="Test", url="https://example.com", source_name="test")
    assert story.summary == ""
    assert story.author == ""
    assert story.extra == {}


def test_base_source_is_abstract():
    with pytest.raises(TypeError):
        BaseSource()  # type: ignore


# ── NewsAPI ───────────────────────────────────────────────────────────────

class TestNewsAPISource:
    def test_skips_when_no_key(self):
        with patch("sources.newsapi.get_settings") as mock_settings:
            mock_settings.return_value.newsapi_key = ""
            source = NewsAPISource()
            result = source.fetch()
        assert result == []

    def test_returns_raw_stories(self):
        mock_article = {
            "title": "AI Makes Breakthrough",
            "url": "https://techcrunch.com/ai-breakthrough",
            "source": {"name": "TechCrunch"},
            "publishedAt": "2024-01-15T10:00:00Z",
            "description": "Researchers have achieved...",
            "author": "Jane Doe",
            "urlToImage": "https://example.com/img.jpg",
            "content": "Full content here...",
        }
        with patch("sources.newsapi.get_settings") as ms, \
             patch("sources.newsapi.requests.get") as mock_get:
            ms.return_value.newsapi_key = "test_key_abc123"
            ms.return_value.geo_focus = "IN"
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"articles": [mock_article]}
            mock_get.return_value.raise_for_status = MagicMock()

            source = NewsAPISource()
            source.limiter = MagicMock()  # Skip rate limiter in tests
            results = source._fetch_headlines()

        assert len(results) == 1
        assert results[0].title == "AI Makes Breakthrough"
        assert results[0].source_name == "TechCrunch"

    def test_skips_removed_articles(self):
        mock_article = {
            "title": "[Removed]",
            "url": "https://example.com",
            "source": {"name": "Test"},
            "publishedAt": None,
            "description": "",
            "author": "",
            "urlToImage": "",
            "content": "",
        }
        with patch("sources.newsapi.get_settings") as ms, \
             patch("sources.newsapi.requests.get") as mock_get:
            ms.return_value.newsapi_key = "test_key"
            ms.return_value.geo_focus = "IN"
            mock_get.return_value.json.return_value = {"articles": [mock_article]}
            mock_get.return_value.raise_for_status = MagicMock()

            source = NewsAPISource()
            source.limiter = MagicMock()
            results = source._fetch_headlines()

        assert results == []


# ── Reddit ────────────────────────────────────────────────────────────────

class TestRedditSource:
    def test_skips_when_no_credentials(self):
        with patch("sources.reddit.get_settings") as ms:
            ms.return_value.reddit_client_id = ""
            ms.return_value.reddit_client_secret = ""
            source = RedditSource()
            result = source.fetch()
        assert result == []


# ── RSS ───────────────────────────────────────────────────────────────────

class TestRSSFeedSource:
    def test_returns_empty_on_bad_feed(self):
        with patch("sources.rss_feeds.RSS_FEEDS", [{"url": "https://bad-url-404.com/rss", "category": "test"}]), \
             patch("feedparser.parse") as mock_parse:
            mock_parse.side_effect = Exception("Connection refused")
            source = RSSFeedSource()
            result = source.fetch()
        assert result == []

    def test_parses_feed_entries(self):
        mock_feed = MagicMock()
        mock_feed.feed.get.return_value = "Test Source"
        mock_entry = MagicMock()
        mock_entry.get = lambda k, d="": {
            "title": "Test Headline",
            "link": "https://example.com/story",
            "summary": "A brief summary.",
        }.get(k, d)
        mock_entry.published_parsed = None
        mock_feed.entries = [mock_entry]

        with patch("sources.rss_feeds.RSS_FEEDS", [{"url": "https://example.com/rss", "category": "tech"}]), \
             patch("feedparser.parse", return_value=mock_feed):
            source = RSSFeedSource()
            source.limiter = MagicMock()
            results = source._fetch_feed("https://example.com/rss", "tech")

        assert len(results) == 1
        assert results[0].title == "Test Headline"
