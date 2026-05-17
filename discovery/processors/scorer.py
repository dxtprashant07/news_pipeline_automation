from .normalizer import NormalizedStory
from core.utils.helpers import utcnow
from core.utils.logger import get_logger

logger = get_logger("processors.scorer")

WEIGHTS = {
    "credibility":  0.40,
    "recency":      0.35,
    "engagement":   0.15,
    "completeness": 0.10,
}


def _recency_score(story: NormalizedStory) -> float:
    age_hours = (utcnow() - story.published_at).total_seconds() / 3600
    return max(0.0, 1.0 - (age_hours / 72))


def _engagement_score(story: NormalizedStory) -> float:
    reddit_score = story.extra.get("score", 0)
    num_comments = story.extra.get("num_comments", 0)
    if reddit_score or num_comments:
        raw = min((reddit_score / 1000) + (num_comments / 200), 1.0)
        return round(raw, 3)
    return 0.5


def _completeness_score(story: NormalizedStory) -> float:
    fields = [story.summary, story.author, story.image_url]
    filled = sum(1 for f in fields if f and len(f) > 3)
    return filled / len(fields)


class PriorityScorer:
    def score(self, story: NormalizedStory) -> NormalizedStory:
        priority = (
            WEIGHTS["credibility"]  * (story.credibility_score / 100) +
            WEIGHTS["recency"]      * _recency_score(story) +
            WEIGHTS["engagement"]   * _engagement_score(story) +
            WEIGHTS["completeness"] * _completeness_score(story)
        )
        story.priority_score = round(priority * 100, 2)
        return story

    def score_all(self, stories: list[NormalizedStory]) -> list[NormalizedStory]:
        for story in stories:
            try:
                self.score(story)
            except Exception as exc:
                logger.warning(f"PriorityScorer error: {exc}")
                story.priority_score = 50.0
        stories.sort(key=lambda s: s.priority_score, reverse=True)
        return stories
