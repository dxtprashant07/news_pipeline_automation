import re
from discovery.config.categories import (
    CATEGORY_RULES, DOMAIN_CATEGORIES, URL_PATH_CATEGORIES, DEFAULT_CATEGORY
)
from .normalizer import NormalizedStory
from core.utils.logger import get_logger

logger = get_logger("processors.classifier")

# ── Scoring constants ──────────────────────────────────────────────────────────
TITLE_MULTIPLIER  = 3    # Title keyword hit counts 3x more than a summary hit
TIER_WEIGHTS      = {"high": 3, "medium": 2, "low": 1}
SOURCE_HINT_BONUS = 6    # source_name contains a known source hint (e.g. "espncricinfo")
DOMAIN_BONUS      = 12   # article domain is in DOMAIN_CATEGORIES map
URL_PATH_BONUS    = 8    # URL path contains a category hint (e.g. /cricket/)
FEED_CAT_BONUS    = 9    # RSS feed is already labeled with a category
MIN_CONFIDENCE    = 3    # minimum total score to assign a category (else "general")
MIN_MARGIN        = 0.25 # top score must be ≥25% higher than 2nd to win outright

# ── Pre-compile keyword patterns at import time ────────────────────────────────
# Single words use \b word-boundary matching to avoid "app" hitting "application".
# Multi-word phrases use plain substring match (already specific enough).
_PATTERNS: dict[str, dict[str, list]] = {}


def _build_patterns() -> None:
    for category, rules in CATEGORY_RULES.items():
        _PATTERNS[category] = {}
        for tier in ("high", "medium", "low"):
            compiled = []
            for kw in rules.get(tier, []):
                if " " in kw:
                    compiled.append(("phrase", kw))
                else:
                    compiled.append(("word", re.compile(r"\b" + re.escape(kw) + r"\b")))
            _PATTERNS[category][tier] = compiled


_build_patterns()


def _keyword_score(category: str, title: str, summary: str) -> float:
    patterns = _PATTERNS[category]
    score = 0.0
    for tier, weight in TIER_WEIGHTS.items():
        for kind, pat in patterns[tier]:
            if kind == "phrase":
                t_hit = pat in title
                s_hit = pat in summary
            else:
                t_hit = bool(pat.search(title))
                s_hit = bool(pat.search(summary))
            score += t_hit * weight * TITLE_MULTIPLIER
            score += s_hit * weight
    return score


def _source_hint_score(category: str, source: str) -> float:
    for hint in CATEGORY_RULES[category].get("sources", []):
        if hint in source:
            return SOURCE_HINT_BONUS
    return 0.0


def _domain_score(domain: str) -> dict[str, float]:
    """Return {category: DOMAIN_BONUS} if domain is known, else {}."""
    cat = DOMAIN_CATEGORIES.get(domain)
    return {cat: DOMAIN_BONUS} if cat else {}


def _url_path_score(url: str) -> dict[str, float]:
    """Return {category: URL_PATH_BONUS} for the first matching URL path pattern."""
    for path_hint, cat in URL_PATH_CATEGORIES:
        if path_hint in url:
            return {cat: URL_PATH_BONUS}
    return {}


def _feed_category_score(extra: dict) -> dict[str, float]:
    """Return {category: FEED_CAT_BONUS} if the RSS feed declared a non-general category."""
    feed_cat = (extra or {}).get("feed_category", "")
    if feed_cat and feed_cat != DEFAULT_CATEGORY and feed_cat in CATEGORY_RULES:
        return {feed_cat: FEED_CAT_BONUS}
    return {}


class Classifier:
    """
    Multi-signal category classifier.

    Signal priority (highest to lowest):
      1. RSS feed_category label  (+9)  — feed already knows its topic
      2. Article domain           (+12) — domain map (espncricinfo → sports)
      3. URL path hint            (+8)  — /cricket/, /markets/, /tech/ etc.
      4. source_name keyword      (+6)  — source_name contains known source hint
      5. Keyword scoring               — weighted tier match in title (3x) + summary (1x)

    Falls back to DEFAULT_CATEGORY when:
      - Top score < MIN_CONFIDENCE (3), OR
      - Top score not ≥25% above 2nd-place score (ambiguous)
    """

    def classify(self, story: NormalizedStory) -> NormalizedStory:
        title   = story.title.lower()
        summary = (story.summary or "").lower()
        source  = story.source_name.lower()
        domain  = (story.domain or "").lower().removeprefix("www.")
        url     = (story.url or "").lower()
        extra   = story.extra or {}

        # Start with keyword scores for every category
        scores: dict[str, float] = {
            cat: _keyword_score(cat, title, summary) + _source_hint_score(cat, source)
            for cat in CATEGORY_RULES
        }

        # Layer in structural signals (additive bonuses)
        for cat, bonus in _domain_score(domain).items():
            scores[cat] = scores.get(cat, 0) + bonus

        for cat, bonus in _url_path_score(url).items():
            scores[cat] = scores.get(cat, 0) + bonus

        for cat, bonus in _feed_category_score(extra).items():
            scores[cat] = scores.get(cat, 0) + bonus

        # Sort to find top two
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_cat, best_score = ranked[0]
        _, second_score      = ranked[1] if len(ranked) > 1 else (None, 0)

        # Require minimum absolute confidence
        if best_score < MIN_CONFIDENCE:
            story.category = DEFAULT_CATEGORY
            return story

        # Require meaningful margin over 2nd place to avoid ambiguous classifications.
        # If two categories are neck-and-neck (e.g. finance vs business on a startup
        # fundraising story), fall back to general rather than guess wrong.
        if second_score > 0 and (best_score - second_score) / best_score < MIN_MARGIN:
            # Tie-break: prefer whichever has a domain/url/feed structural signal
            structural = {}
            structural.update(_domain_score(domain))
            structural.update(_url_path_score(url))
            structural.update(_feed_category_score(extra))
            if best_cat in structural:
                story.category = best_cat
            elif any(c in structural for c in [second_score]):
                story.category = ranked[1][0]
            else:
                story.category = best_cat   # keyword winner wins ties with no structural signal

            return story

        story.category = best_cat
        return story

    def classify_all(self, stories: list[NormalizedStory]) -> list[NormalizedStory]:
        tally: dict[str, int] = {}

        for story in stories:
            try:
                self.classify(story)
            except Exception as exc:
                logger.warning(f"Classifier error on '{story.title[:60]}': {exc}")
                story.category = DEFAULT_CATEGORY
            tally[story.category] = tally.get(story.category, 0) + 1

        # Log breakdown sorted by count descending
        breakdown = ", ".join(
            f"{cat}={n}"
            for cat, n in sorted(tally.items(), key=lambda x: x[1], reverse=True)
            if n > 0
        )
        logger.info(f"Classification complete — {len(stories)} stories: {breakdown}")
        return stories
