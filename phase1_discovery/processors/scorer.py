from .normalizer import NormalizedStory
from ..utils.helpers import utcnow
from ..utils.logger import get_logger

logger = get_logger("processors.scorer")

# Weight config — tweak these to change ranking behaviour
WEIGHTS = {
    "credibility": 0.40,
    "recency":     0.35,
    "engagement":  0.15,
    "completeness": 0.10,
}


def _recency_score(story: NormalizedStory) -> float:
    """1.0 = published now, decays linearly to 0 at 72 hours."""
    age_hours = (utcnow() - story.published_at).total_seconds() / 3600
    return max(0.0, 1.0 - (age_hours / 72))


def _engagement_score(story: NormalizedStory) -> float:
    """Reddit posts carry a score/comment signal; others default to 0.5."""
    reddit_score = story.extra.get("score", 0)
    num_comments = story.extra.get("num_comments", 0)
    if reddit_score or num_comments:
        raw = min((reddit_score / 1000) + (num_comments / 200), 1.0)
        return round(raw, 3)
    return 0.5  # No engagement data — neutral


def _completeness_score(story: NormalizedStory) -> float:
    """Rewards stories that have all metadata fields filled in."""
    fields = [story.summary, story.author, story.image_url]
    filled = sum(1 for f in fields if f and len(f) > 3)
    return filled / len(fields)


class PriorityScorer:
    def score(self, story: NormalizedStory) -> NormalizedStory:
        cred   = story.credibility_score / 100
        rec    = _recency_score(story)
        eng    = _engagement_score(story)
        comp   = _completeness_score(story)

        priority = (
            WEIGHTS["credibility"]  * cred  +
            WEIGHTS["recency"]      * rec   +
            WEIGHTS["engagement"]   * eng   +
            WEIGHTS["completeness"] * comp
        )

        story.priority_score = round(priority * 100, 2)  # 0-100 scale
        return story

    def score_all(self, stories: list[NormalizedStory]) -> list[NormalizedStory]:
        for story in stories:
            try:
                self.score(story)
            except Exception as exc:
                logger.warning(f"PriorityScorer error: {exc}")
                story.priority_score = 50.0

        # Sort highest priority first
        stories.sort(key=lambda s: s.priority_score, reverse=True)
        return stories
