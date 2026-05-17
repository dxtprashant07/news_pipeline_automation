import json
import re

from .ai_client import generate
from .models import SEOMetadata
from .config.style_guide import SEO_SYSTEM_PROMPT
from core.config.settings import get_settings
from core.utils.logger import get_logger

logger = get_logger("writing.seo_optimizer")

_SCHEMA_TEMPLATE = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    "headline": "",
    "description": "",
    "keywords": [],
    "articleSection": "",
    "inLanguage": "en-IN",
}

_SEO_USER_PROMPT = """Generate SEO metadata for this news article and return ONLY valid JSON.

Article headline: {headline}
Article category: {category}
Article excerpt (first 400 chars): {excerpt}

Return JSON with exactly these fields:
{{
  "meta_title": "<headline rephrased for search, 50-60 characters max>",
  "meta_description": "<compelling 1-sentence summary, 140-155 characters max>",
  "focus_keyword": "<single most important search keyword or phrase>",
  "secondary_keywords": ["<keyword 1>", "<keyword 2>", "<keyword 3>", "<keyword 4>"],
  "schema_type": "<NewsArticle | Article | BlogPosting>"
}}"""


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


class SEOOptimizer:
    def __init__(self) -> None:
        self.settings = get_settings()

    def optimize(self, headline: str, category: str, article_html: str) -> SEOMetadata:
        model   = self.settings.resolved_seo_model
        excerpt = _strip_html(article_html)[:400].strip()
        logger.info(f"Generating SEO metadata [{model}] for: '{headline[:60]}'")

        raw = generate(
            model=model,
            anthropic_api_key=self.settings.anthropic_api_key,
            openai_api_key=self.settings.openai_api_key,
            gemini_api_key=self.settings.gemini_api_key,
            system_text=SEO_SYSTEM_PROMPT,
            user_text=_SEO_USER_PROMPT.format(headline=headline, category=category, excerpt=excerpt),
            max_tokens=512,
            cache_system=True,
        )

        try:
            data = _extract_json(raw)
        except json.JSONDecodeError as exc:
            logger.warning(f"SEO JSON parse failed: {exc} — using defaults")
            return self._default_metadata(headline, category)

        schema = dict(_SCHEMA_TEMPLATE)
        schema["@type"]          = data.get("schema_type", "NewsArticle")
        schema["headline"]       = data.get("meta_title", headline)[:110]
        schema["description"]    = data.get("meta_description", "")[:200]
        schema["keywords"]       = [data.get("focus_keyword", "")] + data.get("secondary_keywords", [])
        schema["articleSection"] = category

        return SEOMetadata(
            meta_title=data.get("meta_title", headline)[:100],
            meta_description=data.get("meta_description", "")[:200],
            focus_keyword=data.get("focus_keyword", ""),
            secondary_keywords=data.get("secondary_keywords", [])[:5],
            schema_type=data.get("schema_type", "NewsArticle"),
            schema_markup=schema,
        )

    def _default_metadata(self, headline: str, category: str) -> SEOMetadata:
        schema = dict(_SCHEMA_TEMPLATE)
        schema["headline"]       = headline[:110]
        schema["articleSection"] = category
        return SEOMetadata(meta_title=headline[:100], schema_markup=schema)
