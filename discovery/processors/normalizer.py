from dataclasses import dataclass, field
from datetime import datetime, timezone

from discovery.sources.base import RawStory
from core.utils.helpers import url_hash, content_hash, normalize_url, truncate, domain_from_url, utcnow


@dataclass
class NormalizedStory:
    """Single, consistent schema for every story regardless of source."""
    url_hash: str
    content_hash: str
    title: str
    url: str
    clean_url: str
    domain: str
    summary: str
    author: str
    image_url: str
    source_name: str
    published_at: datetime
    discovered_at: datetime
    category: str = "general"
    credibility_score: int = 0
    priority_score: float = 0.0
    is_duplicate: bool = False
    extra: dict = field(default_factory=dict)


class Normalizer:
    def normalize(self, raw: RawStory) -> NormalizedStory | None:
        title = raw.title.strip()
        url   = raw.url.strip()
        if not title or not url:
            return None

        clean_url = normalize_url(url)
        return NormalizedStory(
            url_hash=url_hash(clean_url),
            content_hash=content_hash(title, raw.source_name),
            title=title,
            url=url,
            clean_url=clean_url,
            domain=domain_from_url(url),
            summary=truncate(raw.summary, 500),
            author=raw.author or "",
            image_url=raw.image_url or "",
            source_name=raw.source_name,
            published_at=raw.published_at or utcnow(),
            discovered_at=utcnow(),
            extra=raw.extra or {},
        )

    def normalize_all(self, raws: list[RawStory]) -> list[NormalizedStory]:
        results = []
        for raw in raws:
            try:
                story = self.normalize(raw)
                if story:
                    results.append(story)
            except Exception:
                pass
        return results
