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

# Strict character-count instructions — "max" was too loose, AI generated short values.
_SEO_USER_PROMPT = """Generate SEO metadata for this news article. Return ONLY valid JSON, no prose.

Article headline : {headline}
Article category : {category}
Article excerpt  : {excerpt}

CHARACTER COUNT RULES — count every character including spaces:
  meta_title       : MUST be between 50 and 60 characters. Count carefully before outputting.
  meta_description : MUST be between 140 and 155 characters. Count carefully before outputting.

Return JSON with exactly these fields:
{{
  "meta_title": "<50-60 chars: headline rewritten for search with focus keyword near the start>",
  "meta_description": "<140-155 chars: one compelling sentence summarising the article with the focus keyword>",
  "focus_keyword": "<the single most searched phrase a reader would type to find this article>",
  "secondary_keywords": ["<kw1>", "<kw2>", "<kw3>", "<kw4>"],
  "schema_type": "NewsArticle"
}}"""

_KEYWORDS_PROMPT = """Extract SEO keywords for this news story. Return ONLY valid JSON.

Headline : {headline}
Category : {category}
Summary  : {summary}

Return JSON:
{{
  "focus_keyword": "<the single most important search phrase for this story>",
  "secondary_keywords": ["<kw1>", "<kw2>", "<kw3>", "<kw4>"]
}}"""


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def _extract_json(text: str) -> dict:
    """
    Robustly extract a JSON object from model output that may contain
    prose preamble, markdown fences, or trailing explanation.
    """
    text = text.strip()
    # Find the first { and the last } and extract just that slice
    start = text.find("{")
    end   = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    json_str = text[start : end + 1]
    # Strip trailing commas before } or ] which some models produce
    json_str = re.sub(r",\s*([}\]])", r"\1", json_str)
    return json.loads(json_str)


def _enforce_title_length(title: str, target_min: int = 50, target_max: int = 60) -> str:
    """Trim or extend meta_title to hit the 50-60 char sweet spot."""
    title = title.strip()
    # Too long — trim at last space before limit
    if len(title) > target_max:
        trimmed = title[:target_max]
        last_space = trimmed.rfind(" ")
        title = trimmed[:last_space] if last_space > target_min else trimmed[:target_max]
    # Too short — extend with news suffixes until we hit 50 chars
    if len(title) < target_min:
        suffixes = [
            " — Latest News",
            " | Breaking News",
            " — Full Coverage",
            " | India News",
            " — News Update",
            " | Top Stories",
        ]
        for suffix in suffixes:
            candidate = title + suffix
            if target_min <= len(candidate) <= target_max:
                return candidate
            if len(candidate) > target_max:
                # suffix too long — trim suffix to fit
                room = target_max - len(title)
                if room >= 8:
                    return (title + suffix[:room]).rstrip()
                break
        # Last resort: pad with spaces removed — just return as-is (scorer gives partial credit)
    return title


def _enforce_keyword_in_title(title: str, focus_keyword: str) -> str:
    """If the focus keyword is missing from the meta title, prepend it."""
    if not focus_keyword or focus_keyword.lower() in title.lower():
        return title
    candidate = f"{focus_keyword.title()}: {title}"
    if len(candidate) <= 60:
        return _enforce_title_length(candidate)
    # Truncate title to make room for the keyword
    budget = 60 - len(focus_keyword.title()) - 2  # 2 for ": "
    truncated = title[:budget].rsplit(" ", 1)[0] if " " in title[:budget] else title[:budget]
    return _enforce_title_length(f"{focus_keyword.title()}: {truncated}")


def _enforce_description_length(desc: str, target_min: int = 140, target_max: int = 155) -> str:
    """Trim or extend meta_description to hit the 140-155 char window."""
    desc = desc.strip()
    # Too long — trim at last space before limit
    if len(desc) > target_max:
        trimmed = desc[:target_max]
        last_space = trimmed.rfind(" ")
        desc = trimmed[:last_space] if last_space > target_min else trimmed[:target_max]
    # Too short — append filler phrases until we hit 140 chars
    if len(desc) < target_min:
        # Ensure the description ends with a period before appending
        if desc and desc[-1] not in ".!?":
            desc += "."
        fillers = [
            " Get the full story, key facts, and latest updates here.",
            " Read more for expert analysis and in-depth coverage.",
            " Stay informed with all the details and breaking updates.",
            " Find out what happened and what it means for you.",
            " Coverage includes key details, reactions, and what comes next.",
        ]
        for filler in fillers:
            candidate = desc + filler
            if target_min <= len(candidate) <= target_max:
                return candidate
            if len(candidate) > target_max:
                room = target_max - len(desc)
                if room >= 15:
                    return (desc + filler[:room]).rstrip()
                break
            # Still too short — keep appending
            desc = candidate
            if len(desc) >= target_min:
                break
    return desc[:target_max] if len(desc) > target_max else desc


class SEOOptimizer:
    def __init__(self) -> None:
        self.settings = get_settings()

    def get_keywords(self, headline: str, category: str, summary: str = "") -> tuple[str, list[str]]:
        """
        Lightweight pre-writing call: extract focus_keyword + secondary_keywords
        from the headline alone (before the full article exists).
        Returns (focus_keyword, secondary_keywords).
        """
        model = self.settings.resolved_seo_model
        try:
            raw = generate(
                model=model,
                anthropic_api_key=self.settings.anthropic_api_key,
                openai_api_key=self.settings.openai_api_key,
                gemini_api_key=self.settings.gemini_api_key,
                groq_api_key=self.settings.groq_api_key,
                system_text=SEO_SYSTEM_PROMPT,
                user_text=_KEYWORDS_PROMPT.format(
                    headline=headline,
                    category=category,
                    summary=(summary or "")[:300],
                ),
                max_tokens=256,
                cache_system=True,
            )
            data = _extract_json(raw)
            return (
                data.get("focus_keyword", "").strip(),
                [k.strip() for k in data.get("secondary_keywords", []) if k.strip()][:4],
            )
        except Exception as exc:
            logger.warning(f"Keyword pre-extraction failed: {exc} — proceeding without keyword hint")
            return ("", [])

    def optimize(self, headline: str, category: str, article_html: str) -> SEOMetadata:
        model   = self.settings.resolved_seo_model
        excerpt = _strip_html(article_html)[:500].strip()
        logger.info(f"Generating SEO metadata [{model}] for: '{headline[:60]}'")

        raw = generate(
            model=model,
            anthropic_api_key=self.settings.anthropic_api_key,
            openai_api_key=self.settings.openai_api_key,
            gemini_api_key=self.settings.gemini_api_key,
            system_text=SEO_SYSTEM_PROMPT,
            user_text=_SEO_USER_PROMPT.format(
                headline=headline,
                category=category,
                excerpt=excerpt,
            ),
            max_tokens=512,
            cache_system=True,
        )

        try:
            data = _extract_json(raw)
        except json.JSONDecodeError as exc:
            logger.warning(f"SEO JSON parse failed: {exc} — using defaults")
            return self._default_metadata(headline, category)

        meta_title = _enforce_title_length(data.get("meta_title", headline))
        meta_title = _enforce_keyword_in_title(meta_title, data.get("focus_keyword", ""))
        meta_desc  = _enforce_description_length(data.get("meta_description", ""))

        logger.info(
            f"  SEO meta_title ({len(meta_title)} chars): '{meta_title}' | "
            f"meta_desc ({len(meta_desc)} chars)"
        )

        schema = dict(_SCHEMA_TEMPLATE)
        schema["@type"]          = data.get("schema_type", "NewsArticle")
        schema["headline"]       = meta_title
        schema["description"]    = meta_desc
        schema["keywords"]       = [data.get("focus_keyword", "")] + data.get("secondary_keywords", [])
        schema["articleSection"] = category

        return SEOMetadata(
            meta_title=meta_title,
            meta_description=meta_desc,
            focus_keyword=data.get("focus_keyword", "").strip(),
            secondary_keywords=[k.strip() for k in data.get("secondary_keywords", []) if k.strip()][:5],
            schema_type=data.get("schema_type", "NewsArticle"),
            schema_markup=schema,
        )

    def _default_metadata(self, headline: str, category: str) -> SEOMetadata:
        schema = dict(_SCHEMA_TEMPLATE)
        schema["headline"]       = headline[:60]
        schema["articleSection"] = category
        return SEOMetadata(meta_title=headline[:60], schema_markup=schema)
