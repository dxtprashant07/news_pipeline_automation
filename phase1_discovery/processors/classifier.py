from ..config.categories import CATEGORIES, DEFAULT_CATEGORY
from .normalizer import NormalizedStory
from ..utils.logger import get_logger

logger = get_logger("processors.classifier")


class Classifier:
    """
    Keyword-based category classifier.
    Scans title + summary for category keywords, picks the best match.
    Falls back to DEFAULT_CATEGORY when nothing matches.
    """

    def classify(self, story: NormalizedStory) -> NormalizedStory:
        text = f"{story.title} {story.summary}".lower()

        scores: dict[str, int] = {}
        for category, keywords in CATEGORIES.items():
            hit_count = sum(1 for kw in keywords if kw in text)
            if hit_count:
                scores[category] = hit_count

        if scores:
            story.category = max(scores, key=lambda c: scores[c])
        else:
            story.category = DEFAULT_CATEGORY

        return story

    def classify_all(self, stories: list[NormalizedStory]) -> list[NormalizedStory]:
        for story in stories:
            try:
                self.classify(story)
            except Exception as exc:
                logger.warning(f"Classifier error on '{story.title[:60]}': {exc}")
                story.category = DEFAULT_CATEGORY
        return stories
