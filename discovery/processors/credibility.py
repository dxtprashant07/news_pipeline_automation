from .normalizer import NormalizedStory
from core.utils.helpers import utcnow
from core.utils.logger import get_logger

logger = get_logger("processors.credibility")

DOMAIN_SCORES: dict[str, int] = {
    # Tier 1 — highly trusted (80-100)
    "reuters.com": 95, "apnews.com": 95, "bbc.com": 92, "bbc.co.uk": 92,
    "thehindu.com": 90, "ndtv.com": 85, "theprint.in": 85,
    "timesofindia.indiatimes.com": 82, "hindustantimes.com": 82,
    "economictimes.indiatimes.com": 85, "livemint.com": 85,
    "businessstandard.com": 85, "financialexpress.com": 82,
    "techcrunch.com": 88, "wired.com": 88, "theverge.com": 85,
    "arstechnica.com": 87, "nature.com": 95, "science.org": 95,
    # Tier 2 — reliable (60-79)
    "indianexpress.com": 80, "scroll.in": 78, "thewire.in": 75,
    "newslaundry.com": 75, "firstpost.com": 72, "news18.com": 70,
    "cnbc.com": 78, "bloomberg.com": 85, "forbes.com": 72,
    "reddit.com": 40,
}

SOURCE_BONUSES: dict[str, int] = {
    "newsapi":       5,
    "rss":           3,
    "reddit":       -10,
    "google_trends": 0,
}


class CredibilityScorer:
    def score(self, story: NormalizedStory) -> NormalizedStory:
        base = DOMAIN_SCORES.get(story.domain, 50)

        for source_key, bonus in SOURCE_BONUSES.items():
            if source_key in story.source_name.lower():
                base += bonus
                break

        age_hours = (utcnow() - story.published_at).total_seconds() / 3600
        if age_hours < 6:
            base += 5
        elif age_hours > 48:
            base -= 10

        if story.image_url:
            base += 2
        if len(story.summary) > 100:
            base += 3

        story.credibility_score = max(0, min(100, base))
        return story

    def score_all(self, stories: list[NormalizedStory]) -> list[NormalizedStory]:
        for story in stories:
            try:
                self.score(story)
            except Exception as exc:
                logger.warning(f"CredibilityScorer error: {exc}")
                story.credibility_score = 50
        return stories
