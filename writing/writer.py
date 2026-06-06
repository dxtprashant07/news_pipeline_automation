import re
import random
import html as html_lib

from .ai_client import generate
from .models import ArticleDraft, SEOMetadata
from .config.style_guide import STYLE_GUIDE, HUMANIZE_PROMPT, EXTEND_PROMPT, REPORTER_PERSONAS, SEO_FIX_PROMPT
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
        (r"\bIn a landmark\b,?\s*",  ""),
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
        (r"\bprovide\b",             "give"),
        (r"\bProvide\b",             "Give"),
        (r"\bensure\b",              "make sure"),
        (r"\bEnsure\b",              "Make sure"),
        (r"\bkey\s+(?=\w)",          ""),
        (r"\bcrucial\b",             "critical"),
        (r"\bvital\b",               "important"),
        (r"\blandscape\b",           "space"),
        (r"\becosystem\b",           "network"),
        (r"\bstakeholders\b",        "those involved"),
        (r"\bStakeholders\b",        "Those involved"),
        (r"\binitiative\b",          "push"),
        (r"\bInitiative\b",          "Push"),
        (r"\bchallenge\b",           "problem"),
        (r"\bChallenge\b",           "Problem"),
        (r"\bThis comes as\b",       ""),
        (r"\bAmid\b(?!\s+the\s+backdrop)", "As"),
        (r"\bSeek to\b",             "Want to"),
        (r"\bseek to\b",             "want to"),
        (r"\baim to\b",              "plan to"),
        (r"\bAim to\b",              "Plan to"),
    ]
    for pattern, replacement in REPLACEMENTS:
        html = re.sub(pattern, replacement, html)

    # 2. Randomised synonyms — same word maps to a different replacement each run.
    # This raises perplexity scores by making word choice genuinely unpredictable.
    RANDOM_SYNONYMS = [
        (r"\bincreased\b",   ["climbed", "jumped", "grew", "rose", "went up"]),
        (r"\bIncreased\b",   ["Climbed", "Jumped", "Grew", "Rose"]),
        (r"\bdecreased\b",   ["fell", "dropped", "slipped", "eased", "came down"]),
        (r"\bDecreased\b",   ["Fell", "Dropped", "Slipped", "Eased"]),
        (r"\bannounced\b",   ["said", "confirmed", "put out", "told reporters"]),
        (r"\bAnnounced\b",   ["Said", "Confirmed", "Put out"]),
        (r"\bmeeting\b",     ["talks", "session", "huddle", "sit-down"]),
        (r"\bMeeting\b",     ["Talks", "Session", "Huddle"]),
        (r"\bissue\b",       ["problem", "matter", "question", "headache"]),
        (r"\bIssue\b",       ["Problem", "Matter", "Question"]),
        (r"\bstated\b",      ["said", "put it", "told reporters"]),
        (r"\bStated\b",      ["Said", "Put it"]),
        (r"\bnoted\b",       ["said", "pointed out", "added"]),
        (r"\bNoted\b",       ["Said", "Pointed out", "Added"]),
        (r"\bhighlighted\b", ["pointed to", "flagged", "stressed", "mentioned"]),
        (r"\bHighlighted\b", ["Pointed to", "Flagged", "Stressed"]),
        (r"\bremains\b",     ["is still", "stays", "continues to be"]),
        (r"\bRemains\b",     ["Is still", "Stays", "Continues to be"]),
        (r"\blarge\b",       ["big", "sizable", "hefty", "major"]),
        (r"\bLarge\b",       ["Big", "Sizable", "Hefty"]),
        (r"\bsmall\b",       ["modest", "limited", "slim", "minor"]),
        (r"\bSmall\b",       ["Modest", "Limited", "Slim"]),
        (r"\bquickly\b",     ["fast", "swiftly", "rapidly", "in short order"]),
        (r"\bslowly\b",      ["gradually", "over time", "in stages"]),
        (r"\bexpected\b",    ["likely", "set", "due", "anticipated"]),
        (r"\bExpected\b",    ["Likely", "Set", "Due"]),
        (r"\bnumerous\b",    ["many", "several", "a string of", "a host of"]),
        (r"\bNumerous\b",    ["Many", "Several", "A host of"]),
        (r"\battempt\b",     ["try", "bid", "push", "effort"]),
        (r"\bAttempt\b",     ["Try", "Bid", "Push"]),
        (r"\bapproach\b",    ["way", "path", "method", "tactic"]),
        (r"\bApproach\b",    ["Way", "Path", "Method"]),
    ]
    for pattern, alternatives in RANDOM_SYNONYMS:
        html = re.sub(pattern, lambda _m, a=alternatives: random.choice(a), html)

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


def _extract_new_paragraphs(raw: str) -> str:
    """
    Pull only <p> and <h2> tags from the extension model's output.
    The model is asked to return new paragraphs only, but may include prose preamble.
    """
    raw = raw.strip()
    # Strip markdown fences if present
    raw = re.sub(r"^```(?:html)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    # Extract all <p> and <h2> blocks — ignore anything outside tags
    tags = re.findall(r"<(?:p|h2)[^>]*>.*?</(?:p|h2)>", raw, re.IGNORECASE | re.DOTALL)
    return "\n".join(tags).strip()


def _append_before_last_p(article_html: str, new_content: str) -> str:
    """Insert new_content before the final <p> block so the closing paragraph stays last."""
    if not new_content:
        return article_html
    # Find the start of the last <p>...</p>
    matches = list(re.finditer(r"<p[^>]*>.*?</p>", article_html, re.IGNORECASE | re.DOTALL))
    if len(matches) >= 2:
        insert_at = matches[-1].start()
        return article_html[:insert_at] + new_content + "\n" + article_html[insert_at:]
    # Only one paragraph or none — just append
    return article_html + "\n" + new_content


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
        # Budget: ~1.4 tokens/word for content + overhead for system prompt.
        # Groq caps at 8192 per call — _call_groq enforces that internally.
        max_tokens = max(4096, int(wc * 6))

        # Pick a random reporter persona for voice variety
        persona = random.choice(REPORTER_PERSONAS)
        logger.info(
            f"Writing [{model}, {wc}w, persona={REPORTER_PERSONAS.index(persona)}] "
            f"story {story.id}: '{story.title[:55]}'"
        )

        _gen_kwargs = dict(
            model=model,
            anthropic_api_key=self.settings.anthropic_api_key,
            openai_api_key=self.settings.openai_api_key,
            gemini_api_key=self.settings.gemini_api_key,
            groq_api_key=self.settings.groq_api_key,
            max_tokens=max_tokens,
        )

        # ── Pass 1: Write draft (with retry on short output) ──────────────────
        draft_html  = ""
        draft_words = 0
        for attempt in range(1, 4):       # up to 3 attempts
            draft_raw  = generate(
                **_gen_kwargs,
                system_text=STYLE_GUIDE.format(word_count=wc),
                user_text=self._build_user_message(
                    story, verification,
                    focus_keyword=focus_keyword,
                    secondary_keywords=secondary_keywords or [],
                    persona=persona,
                ),
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

        # ── Pass 1b: Append new paragraphs until target word count is reached ──
        for ext_round in range(1, 4):          # up to 3 extension rounds
            if draft_words >= int(wc * 0.97):  # within 3% of target — done
                break
            needed = wc - draft_words
            logger.info(
                f"  Extend round {ext_round}: {draft_words}w → target {wc}w "
                f"(need ~{needed}w more)"
            )
            ext_raw = generate(
                **_gen_kwargs,
                system_text=EXTEND_PROMPT,
                user_text=self._build_extend_message(draft_html, draft_words, wc),
                cache_system=False,
            )
            # The model returns ONLY the new paragraphs — extract and append
            new_paras = _extract_new_paragraphs(ext_raw)
            new_words = _count_words(new_paras)
            if new_words < 30:
                logger.warning(f"  Extend round {ext_round}: got too few words ({new_words}w) — stopping")
                break
            # Append before the last <p> so the closing paragraph stays at the end
            draft_html  = _append_before_last_p(draft_html, new_paras)
            prev_words  = draft_words
            draft_words = _count_words(draft_html)
            logger.info(f"  Extend round {ext_round}: {prev_words}w → {draft_words}w (+{new_words}w)")

        # ── Pass 2: Humanize ──────────────────────────────────────────────────
        humanized_raw = generate(
            **_gen_kwargs,
            system_text=HUMANIZE_PROMPT,
            user_text=draft_html,
            cache_system=False,
        )
        humanized_html = _clean_article_html(humanized_raw)

        humanized_words = _count_words(humanized_html)
        if humanized_words < draft_words * 0.88:
            logger.warning(
                f"  Humanizer shrunk {draft_words}→{humanized_words}w — keeping draft."
            )
            humanized_html = draft_html

        # ── Pass 3: SEO fix (only if structural gaps found) ──────────────────
        h2_count  = len(re.findall(r"<h2[^>]*>", humanized_html, re.IGNORECASE))
        plain     = re.sub(r"<[^>]+>", " ", humanized_html).lower()
        kw_lower  = focus_keyword.lower()
        first_p   = re.search(r"<p[^>]*>(.*?)</p>", humanized_html, re.IGNORECASE | re.DOTALL)
        kw_in_open = kw_lower in re.sub(r"<[^>]+>", " ", first_p.group(1)).lower() if first_p else False
        missing_sec = [k for k in (secondary_keywords or []) if k.lower() not in plain]

        needs_seo_fix = h2_count < 2 or not kw_in_open or len(missing_sec) >= 1
        if needs_seo_fix:
            issues = []
            if h2_count < 2:
                issues.append(f"missing H2 subheadings (found {h2_count}, need at least 2)")
            if not kw_in_open:
                issues.append(f'focus keyword "{focus_keyword}" not in opening paragraph')
            if missing_sec:
                issues.append(f"missing secondary keywords: {', '.join(missing_sec)}")
            logger.info(f"  SEO fix pass — {'; '.join(issues)}")
            fix_raw = generate(
                **_gen_kwargs,
                system_text=SEO_FIX_PROMPT,
                user_text=self._build_seo_fix_message(
                    humanized_html, focus_keyword, secondary_keywords or [],
                    h2_count, kw_in_open, missing_sec,
                ),
                cache_system=False,
            )
            fixed = _clean_article_html(fix_raw)
            if _count_words(fixed) >= _count_words(humanized_html) * 0.85:
                humanized_html = fixed
            else:
                logger.warning("  SEO fix shrunk article too much — keeping humanized version")

        # ── Pass 4: Rule-based post-processing ───────────────────────────────
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
**SEO Requirements** (HARD — article is scored algorithmically):
- FOCUS KEYWORD: "{focus_keyword}"
  → MUST appear in the FIRST SENTENCE of the FIRST paragraph
  → Use naturally 3-5 times total across the full article
- SECONDARY KEYWORDS — include EACH of these at least once in the body: {kw_list or "(none)"}
- SUBHEADINGS: Include at least 2 <h2> tags. No fewer.
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

    def _build_extend_message(self, article_html: str, current_words: int, target_words: int) -> str:
        needed = target_words - current_words
        # Send only the last 2 paragraphs as context — enough for natural continuation
        # while keeping the request small (avoids Groq TPM overflow).
        paragraphs = re.findall(r"<p[^>]*>.*?</p>", article_html, re.IGNORECASE | re.DOTALL)
        tail = "\n".join(paragraphs[-2:]) if len(paragraphs) >= 2 else article_html
        return (
            f"Add approximately {needed} more words to this news article. "
            f"Continue naturally from the last paragraphs shown below.\n\n"
            f"LAST PARAGRAPHS:\n{tail}\n\n"
            f"Output ONLY the new <p> paragraphs to add. Do not repeat anything above."
        )

    def _build_seo_fix_message(
        self,
        article_html: str,
        focus_keyword: str,
        secondary_keywords: list[str],
        h2_count: int,
        kw_in_open: bool,
        missing_sec: list[str],
    ) -> str:
        issues = []
        if h2_count < 2:
            issues.append(
                f"- ADD subheadings: the article has only {h2_count} <h2> tag(s). "
                "Add subheadings so there are at least 2 total. "
                "Place them at natural section breaks. Make them sound like a real editor wrote them."
            )
        if not kw_in_open:
            issues.append(
                f'- ADD FOCUS KEYWORD to opening: "{focus_keyword}" must appear in the first <p> paragraph, '
                "within the first two sentences. Edit the opening to include it naturally."
            )
        if missing_sec:
            kw_list = ", ".join(f'"{k}"' for k in missing_sec)
            issues.append(
                f"- ADD MISSING KEYWORDS: these secondary keywords do not appear in the article and must be "
                f"woven in naturally at least once each: {kw_list}"
            )
        issues_text = "\n".join(issues)
        return f"""Fix the following SEO issues in this article. Make ONLY the minimal changes needed to address each issue. \
Do not rewrite paragraphs that are already fine. Preserve all existing HTML structure, style, and content.

ISSUES TO FIX:
{issues_text}

ARTICLE TO FIX:
{article_html}

Output the complete fixed HTML article body only. No preamble, no commentary."""
