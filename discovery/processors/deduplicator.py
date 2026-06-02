import re
from .normalizer import NormalizedStory
from core.utils.logger import get_logger

logger = get_logger("processors.deduplicator")

# Jaccard similarity threshold — titles sharing >55% of meaningful words
# are treated as the same story from different sources.
TITLE_SIMILARITY_THRESHOLD = 0.55

_STOPWORDS = frozenset({
    "the", "a", "an", "is", "in", "on", "at", "to", "for", "of", "and",
    "or", "but", "with", "from", "by", "as", "be", "its", "it", "his",
    "her", "their", "this", "that", "are", "was", "were", "has", "have",
    "had", "will", "new", "over", "after", "says", "say", "said",
})


def _title_words(title: str) -> frozenset[str]:
    """Return meaningful words from a title (lowercase, no stopwords, no punctuation)."""
    words = re.sub(r"[^\w\s]", "", title.lower()).split()
    return frozenset(w for w in words if w not in _STOPWORDS and len(w) > 2)


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class Deduplicator:
    """
    Three-pass deduplication:
    1. URL hash      — exact same URL
    2. Content hash  — same title + source (cross-source reposts)
    3. Title similarity — Jaccard overlap > 55% within the current batch
                          (catches same event covered by multiple feeds)
    """

    def deduplicate(
        self,
        stories: list[NormalizedStory],
        existing_url_hashes: set[str] | None = None,
        existing_content_hashes: set[str] | None = None,
    ) -> list[NormalizedStory]:
        seen_urls    = set(existing_url_hashes    or [])
        seen_content = set(existing_content_hashes or [])

        unique: list[NormalizedStory] = []
        hash_dupes  = 0
        title_dupes = 0

        # Pre-compute word sets for stories already accepted (for similarity check)
        accepted_word_sets: list[frozenset] = []

        for story in stories:
            # Pass 1 + 2: hash-based
            if story.url_hash in seen_urls or story.content_hash in seen_content:
                story.is_duplicate = True
                hash_dupes += 1
                continue

            # Pass 3: title similarity against already-accepted stories in this batch
            words = _title_words(story.title)
            is_similar = any(
                _jaccard(words, existing_words) >= TITLE_SIMILARITY_THRESHOLD
                for existing_words in accepted_word_sets
            )
            if is_similar:
                story.is_duplicate = True
                title_dupes += 1
                continue

            seen_urls.add(story.url_hash)
            seen_content.add(story.content_hash)
            accepted_word_sets.append(words)
            unique.append(story)

        logger.info(
            f"Deduplicator: {len(unique)} unique | "
            f"{hash_dupes} hash dupes | {title_dupes} title-similar dupes "
            f"(from batch of {len(stories)})"
        )
        return unique
