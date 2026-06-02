import re
import random
import html as html_lib

from .ai_client import generate
from .models import ArticleDraft, SEOMetadata
from .config.style_guide import STYLE_GUIDE, HUMANIZE_PROMPT, REPORTER_PERSONAS
from verification.models import VerificationResult
from core.config.settings import get_settings
from core.utils.logger import get_logger

logger = get_logger("writing.writer")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _count_words(html: str) -> int:
    return len(re.sub(r"<[^>]+>", " ", html).split())


def _clean_article_html(raw: str) -> str:
    """
    Extract only the HTML article body from the model's raw output.
    Models like Gemini prepend prose or wrap output in markdown -- strip all of that.
    """
    raw = raw.strip()
    first_tag = re.search(r"<(p|h[1-6]|ul|ol|blockquote)[^>]*>", raw, re.IGNORECASE)
    last_tag  = re.search(
        r"</(p|h[1-6]|ul|ol|blockquote)>(?!.*</(p|h[1-6]|ul|ol|blockquote)>)",
        raw, re.IGNORECASE | re.DOTALL,
    )
    if first_tag and last_tag:
        return raw[first_tag.start() : last_tag.end()].strip()
    raw = re.sub(r"^```(?:html)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _post_process(html: str) -> str:
    """
    Rule-based post-processing applied after both AI passes.
    Catches AI patterns that both prompts missed and adds deterministic
    human touches that no language model reliably adds on its own.
    """
    # 1. Replace the most persistent AI fingerprint phrases
    REPLACEMENTS = [
        (r"\bFurthermore\b,?\s*",    "And "),
        (r"\bMoreover\b,?\s*",       "What's more, "),
        (r"\bAdditionally\b,?\s*",   "Also, "),
        (r"\bIn addition\b,?\s*",    "On top of that, "),
        (r"\bIt is worth noting that\s*", ""),
        (r"\bIt should be noted that\s*", ""),
        (r"\bNotably,\s*",           ""),
        (r"\bIn conclusion\b,?\s*",  ""),
        (r"\bTo summarise\b,?\s*",   ""),
        (r"\bTo summarize\b,?\s*",   ""),
        (r"\bIn summary\b,?\s*",     ""),
        (r"\bNeedless to say,?\s*",  ""),
        (r"\bIt goes without saying that\s*", ""),
        (r"\bIn a significant development\b,?\s*", ""),
        (r"\bIn a major development\b,?\s*", ""),
        (r"\bMoving forward\b,?\s*", "Going ahead, "),
        (r"\bGoing forward\b,?\s*",  "Going ahead, "),
        (r"\bLeverage\b",            "use"),
        (r"\bleveraging\b",          "using"),
        (r"\bUtilize\b",             "Use"),
        (r"\butilize\b",             "use"),
        (r"\bUtilised\b",            "Used"),
        (r"\butilised\b",            "used"),
        (r"\bSubstantial\b",         "Sizeable"),
        (r"\bsubstantial\b",         "sizeable"),
        (r"\bSignificant\b(?!\s+figures|\s+number)", "Notable"),
        (r"\bsignificant\b(?!\s+figures|\s+number)", "notable"),
        (r"\bdemonstrated\b",        "showed"),
        (r"\bDemonstrated\b",        "Showed"),
        (r"\bconducted\b",           "carried out"),
        (r"\bConducted\b",           "Carried out"),
        (r"\bimplemented\b",         "rolled out"),
        (r"\bImplemented\b",         "Rolled out"),
        (r"\bin order to\b",         "to"),
        (r"\bdue to the fact that\b", "because"),
        (r"\bat this point in time\b", "now"),
        (r"\bprior to\b",            "before"),
        (r"\bsubsequently\b",        "later"),
        (r"\bcommenced\b",           "started"),
        (r"\bpurchased\b",           "bought"),
        (r"\bobtained\b",            "got"),
        (r"\bapproximately\b",       "about"),
        (r"\bfacilitate\b",          "help"),
        (r"\bascertain\b",           "find out"),
        (r"\bendeavour\b",           "try"),
    ]
    for pattern, replacement in REPLACEMENTS:
        html = re.sub(pattern, replacement, html)

    # 2. Fix double spaces or sentence starts left by replacements
    html = re.sub(r"  +", " ", html)
    html = re.sub(r"(<p[^>]*>)\s+", r"\1", html)

    # 3. Ensure contractions (AI often misses these even when prompted)
    CONTRACTIONS = [
        (r"\bit is\b(?! not)",   "it's"),
        (r"\bIt is\b(?! not)",   "It's"),
        (r"\bdo not\b",          "don't"),
        (r"\bDo not\b",          "Don't"),
        (r"\bdoes not\b",        "doesn't"),
        (r"\bDoes not\b",        "Doesn't"),
        (r"\bdid not\b",         "didn't"),
        (r"\bDid not\b",         "Didn't"),
        (r"\bis not\b",          "isn't"),
        (r"\bIs not\b",          "Isn't"),
        (r"\bwill not\b",        "won't"),
        (r"\bWill not\b",        "Won't"),
        (r"\bwould not\b",       "wouldn't"),
        (r"\bWould not\b",       "Wouldn't"),
        (r"\bhas not\b",         "hasn't"),
        (r"\bHas not\b",         "Hasn't"),
        (r"\bhave not\b",        "haven't"),
        (r"\bHave not\b",        "Haven't"),
        (r"\bcannot\b",          "can't"),
        (r"\bCannot\b",          "Can't"),
        (r"\bthey are\b",        "they're"),
        (r"\bThey are\b",        "They're"),
        (r"\bthat is\b",         "that's"),
        (r"\bThat is\b",         "That's"),
        (r"\bthere is\b",        "there's"),
        (r"\bThere is\b",        "There's"),
        (r"\bwhat is\b",         "what's"),
        (r"\bWhat is\b",         "What's"),
    ]
    # Apply contractions only inside text content (not inside HTML tag attributes).
    # Strategy: split on tags, apply to text nodes only, then rejoin.
    parts = re.split(r"(<[^>]+>)", html)
    result_parts = []
    for part in parts:
        if part.startswith("<"):
            result_parts.append(part)   # HTML tag — leave untouched
        else:
            for pattern, replacement in CONTRACTIONS:
                part = re.sub(pattern, replacement, part)
            result_parts.append(part)
    html = "".join(result_parts)

    return html


def _format_sources(verification: VerificationResult) -> str:
    if not verification.sources_found:
        return "No additional sources available."
    return "\n".join(
        f"- {s.title or s.domain} ({s.url})"
        for s in verification.sources_found[:5]
    )


# ── ArticleWriter ─────────────────────────────────────────────────────────────

class ArticleWriter:
    """
    Writes a full HTML article for a verified story.
    Two AI passes (write → humanize) + one rule-based post-processing pass.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def write(
        self,
        story,
        verification: VerificationResult,
        word_count: int | None = None,
        ai_model: str | None = None,
        focus_keyword: str = "",
        secondary_keywords: list[str] | None = None,
    ) -> ArticleDraft:
        model = ai_model   if ai_model   is not None else self.settings.article_model
        wc    = word_count if word_count is not None else self.settings.article_word_count
        max_tokens = max(self.settings.article_max_tokens, int(wc * 3))

        # Pick a random reporter persona for voice variety
        persona = random.choice(REPORTER_PERSONAS)
        logger.info(
            f"Writing [{model}, {wc}w, persona={REPORTER_PERSONAS.index(persona)}] "
            f"story {story.id}: '{story.title[:55]}'"
        )

        # ── Pass 1: Write draft (with retry on short output) ──────────────────
        draft_html  = ""
        draft_words = 0
        for attempt in range(1, 4):       # up to 3 attempts
            draft_raw  = generate(
                model=model,
                anthropic_api_key=self.settings.anthropic_api_key,
                openai_api_key=self.settings.openai_api_key,
                gemini_api_key=self.settings.gemini_api_key,
                system_text=STYLE_GUIDE.format(word_count=wc),
                user_text=self._build_user_message(
                    story, verification,
                    focus_keyword=focus_keyword,
                    secondary_keywords=secondary_keywords or [],
                    persona=persona,
                ),
                max_tokens=max_tokens,
                cache_system=True,
            )
            draft_html  = _clean_article_html(draft_raw)
            draft_words = _count_words(draft_html)

            if draft_words >= 200:
                if attempt > 1:
                    logger.info(f"  Draft OK on attempt {attempt} ({draft_words}w)")
                break

            logger.warning(
                f"  Draft attempt {attempt}/3 too short ({draft_words}w). "
                f"Raw preview: {repr(draft_raw[:300])}"
            )
            if attempt == 3:
                raise ValueError(
                    f"Model '{model}' returned only {draft_words} words after 3 attempts "
                    f"for story {story.id}."
                )

        # ── Pass 2: Humanize ──────────────────────────────────────────────────
        humanized_raw = generate(
            model=model,
            anthropic_api_key=self.settings.anthropic_api_key,
            openai_api_key=self.settings.openai_api_key,
            gemini_api_key=self.settings.gemini_api_key,
            system_text=HUMANIZE_PROMPT,
            user_text=draft_html,
            max_tokens=max_tokens,
            cache_system=False,
        )
        humanized_html = _clean_article_html(humanized_raw)

        humanized_words = _count_words(humanized_html)
        if humanized_words < draft_words * 0.65:
            logger.warning(
                f"  Humanizer shrunk {draft_words}→{humanized_words}w — keeping draft."
            )
            humanized_html = draft_html

        # ── Pass 3: Rule-based post-processing ───────────────────────────────
        article_html  = _post_process(humanized_html)
        final_words   = _count_words(article_html)

        logger.info(f"  Done — {final_words}w (draft={draft_words}, humanized={humanized_words})")

        return ArticleDraft(
            story_id=story.id,
            headline=story.title,
            article_html=article_html,
            word_count=final_words,
            seo=SEOMetadata(),
            category=story.category,
            source_url=story.url,
            ai_model_used=model,
        )

    def _build_user_message(
        self,
        story,
        verification: VerificationResult,
        focus_keyword: str = "",
        secondary_keywords: list[str] | None = None,
        persona: str = "",
    ) -> str:
        seo_block = ""
        if focus_keyword:
            kw_list = ", ".join(f'"{k}"' for k in (secondary_keywords or []))
            seo_block = f"""
**SEO Requirements** (mandatory — article is scored on these):
- FOCUS KEYWORD: "{focus_keyword}"
  → Must appear in the first paragraph, first 2 sentences preferred
  → Use naturally 3-5 times total — do not stuff it
- SECONDARY KEYWORDS (include each at least once): {kw_list or "(none)"}
"""

        persona_block = f"\n**Your writing style for this article**: {persona}\n" if persona else ""

        return f"""Write a news article for the following story.

**Headline**: {story.title}
**Category**: {story.category}

**Original summary**:
{story.summary or "(no summary available)"}

**Source**: {story.source_name} — {story.url}

**Corroborating sources**:
{_format_sources(verification)}
{seo_block}{persona_block}
Output HTML article body only. No preamble, no closing note, no markdown."""
