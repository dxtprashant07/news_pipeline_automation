import re
from .normalizer import NormalizedStory
from core.utils.logger import get_logger

logger = get_logger("processors.sanitizer")

_DANGEROUS_PATTERNS = [
    re.compile(r"<script[\s\S]*?>[\s\S]*?</script>", re.I),
    re.compile(r"javascript\s*:", re.I),
    re.compile(r"on\w+\s*=\s*[\"'][^\"']*[\"']", re.I),
    re.compile(r"<iframe[\s\S]*?>", re.I),
    re.compile(r"<object[\s\S]*?>", re.I),
    re.compile(r"<embed[\s\S]*?>",  re.I),
    re.compile(r"data:\s*text/html", re.I),
]

_ALL_HTML_TAGS = re.compile(r"<[^>]+>")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MAX_FIELD_LEN = {"title": 500, "summary": 2000, "author": 200, "image_url": 1000}


def _clean(text: str, max_len: int = 2000) -> str:
    if not text:
        return ""
    for pattern in _DANGEROUS_PATTERNS:
        text = pattern.sub("", text)
    text = _ALL_HTML_TAGS.sub("", text)
    text = _CONTROL_CHARS.sub("", text)
    text = " ".join(text.split())
    return text[:max_len]


def _safe_url(url: str) -> str:
    stripped = url.strip().lower()
    if stripped.startswith(("javascript:", "data:", "vbscript:")):
        logger.warning(f"Sanitizer blocked dangerous URL scheme: {url[:80]}")
        return ""
    return url[:_MAX_FIELD_LEN["image_url"]]


class Sanitizer:
    def sanitize(self, story: NormalizedStory) -> NormalizedStory:
        story.title     = _clean(story.title,     _MAX_FIELD_LEN["title"])
        story.summary   = _clean(story.summary,   _MAX_FIELD_LEN["summary"])
        story.author    = _clean(story.author,    _MAX_FIELD_LEN["author"])
        story.image_url = _safe_url(story.image_url)
        return story

    def sanitize_all(self, stories: list[NormalizedStory]) -> list[NormalizedStory]:
        cleaned = []
        for story in stories:
            try:
                cleaned.append(self.sanitize(story))
            except Exception as exc:
                logger.warning(f"Sanitizer skipped '{story.title[:60]}': {exc}")
        return cleaned
