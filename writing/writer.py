import re

from .ai_client import generate
from .models import ArticleDraft, SEOMetadata
from .config.style_guide import STYLE_GUIDE
from verification.models import VerificationResult
from core.config.settings import get_settings
from core.utils.logger import get_logger

logger = get_logger("writing.writer")


def _count_words(html: str) -> int:
    return len(re.sub(r"<[^>]+>", " ", html).split())


def _format_sources(verification: VerificationResult) -> str:
    if not verification.sources_found:
        return "No additional sources available."
    return "\n".join(
        f"- {s.title or s.domain} ({s.url})"
        for s in verification.sources_found[:5]
    )


class ArticleWriter:
    """
    Writes a full HTML article for a verified story.
    One instance per pipeline run — settings loaded once.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def write(self, story, verification: VerificationResult) -> ArticleDraft:
        model = self.settings.article_model
        logger.info(f"Writing article [{model}] for story {story.id}: '{story.title[:60]}'")

        article_html = generate(
            model=model,
            anthropic_api_key=self.settings.anthropic_api_key,
            openai_api_key=self.settings.openai_api_key,
            gemini_api_key=self.settings.gemini_api_key,
            system_text=STYLE_GUIDE.format(word_count=self.settings.article_word_count),
            user_text=self._build_user_message(story, verification),
            max_tokens=self.settings.article_max_tokens,
            cache_system=True,
        )

        word_count = _count_words(article_html)
        logger.info(f"  Article written — {word_count} words")

        return ArticleDraft(
            story_id=story.id,
            headline=story.title,
            article_html=article_html,
            word_count=word_count,
            seo=SEOMetadata(),
            category=story.category,
            source_url=story.url,
            ai_model_used=model,
        )

    def _build_user_message(self, story, verification: VerificationResult) -> str:
        return f"""Write a news article for the following story.

**Headline**: {story.title}

**Category**: {story.category}

**Original summary**:
{story.summary or "(no summary available)"}

**Source**: {story.source_name} — {story.url}

**Corroborating sources confirmed by fact-check**:
{_format_sources(verification)}

Follow the style guide exactly. Output HTML article body only."""
