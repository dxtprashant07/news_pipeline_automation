from .normalizer import NormalizedStory
from core.utils.logger import get_logger

logger = get_logger("processors.deduplicator")


class Deduplicator:
    """
    Two-pass deduplication:
    1. URL hash  — exact same URL
    2. Content hash — same title + source (catches cross-source reposts)

    Also checks hashes already stored in the DB to avoid re-inserting
    stories discovered in previous scheduler runs.
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
        dupes = 0

        for story in stories:
            if story.url_hash in seen_urls or story.content_hash in seen_content:
                story.is_duplicate = True
                dupes += 1
                continue
            seen_urls.add(story.url_hash)
            seen_content.add(story.content_hash)
            unique.append(story)

        logger.info(
            f"Deduplicator: {len(unique)} unique, {dupes} duplicates removed "
            f"(from batch of {len(stories)})"
        )
        return unique
