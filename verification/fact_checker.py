"""
Fact Verification Agent — implements the 3-source rule.

Primary (BING_SEARCH_API_KEY set):
  Search Bing for the headline → count distinct Tier 1/2 sources →
  approve if >= min_verification_sources, reject otherwise.

Fallback (no API key):
  Use Phase 1 credibility_score. Approve if >= credibility_threshold.
"""
import re
from urllib.parse import urlparse

import requests

from .models import VerificationResult, VerificationStatus, SourceMatch
from core.config.settings import get_settings
from core.utils.logger import get_logger

logger = get_logger("verification.fact_checker")

TIER1_DOMAINS: frozenset[str] = frozenset({
    # International wire services
    "reuters.com", "apnews.com", "afp.com",
    # International broadcasters
    "bbc.com", "bbc.co.uk", "aljazeera.com",
    # Indian Tier-1 newspapers / outlets
    "thehindu.com", "ndtv.com", "theprint.in",
    "timesofindia.indiatimes.com", "hindustantimes.com",
    "indianexpress.com",
    # Indian financial press
    "economictimes.indiatimes.com", "livemint.com",
    "businessstandard.com", "financialexpress.com",
    "moneycontrol.com",
    # International financial press
    "bloomberg.com", "wsj.com", "ft.com",
    # Science / government
    "nature.com", "science.org", "who.int",
    "pib.gov.in", "mygov.in",                    # Indian government press releases
})

TIER2_DOMAINS: frozenset[str] = frozenset({
    # Indian digital news
    "scroll.in", "thewire.in", "newslaundry.com",
    "firstpost.com", "news18.com", "zeenews.india.com",
    "indiatoday.in", "deccanherald.com", "telegraphindia.com",
    "tribuneindia.com", "dnaindia.com", "freepressjournal.in",
    # Indian business / tech
    "inc42.com", "yourstory.com", "entrackr.com", "techcircle.in",
    "bgr.in", "gadgets360.com",
    # Sports
    "espncricinfo.com", "cricbuzz.com", "sportskeeda.com",
    # International
    "cnbc.com", "techcrunch.com", "wired.com",
    "theverge.com", "arstechnica.com", "forbes.com",
    "theguardian.com", "nytimes.com", "washingtonpost.com",
})

BING_SEARCH_URL = "https://api.bing.microsoft.com/v7.0/search"


def _classify_domain(domain: str) -> int:
    domain = domain.lower().lstrip("www.")
    if domain in TIER1_DOMAINS or domain.endswith((".gov", ".gov.in", ".edu")):
        return 1
    if domain in TIER2_DOMAINS:
        return 2
    return 3


def _domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


class FactChecker:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._fallback_warned = False

    def check(self, story) -> VerificationResult:
        try:
            if self.settings.bing_search_api_key:
                return self._verify_with_bing(story)
            return self._verify_with_fallback(story)
        except Exception as exc:
            logger.error(f"FactChecker error for story {story.id}: {exc!r}")
            return VerificationResult(
                story_id=story.id,
                status=VerificationStatus.ERROR,
                source_count=0,
                rejection_reason=f"Verification error: {exc}",
            )

    def _verify_with_bing(self, story) -> VerificationResult:
        query = re.sub(r"\s+", " ", story.title).strip()[:100]
        logger.info(f"Bing search: '{query[:60]}'")

        try:
            resp = requests.get(
                BING_SEARCH_URL,
                headers={"Ocp-Apim-Subscription-Key": self.settings.bing_search_api_key},
                params={"q": query, "count": 10, "mkt": "en-IN"},
                timeout=self.settings.verification_timeout_seconds,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning(f"Bing API failed ({exc!r}), falling back to credibility check")
            return self._verify_with_fallback(story)

        results = resp.json().get("webPages", {}).get("value", [])
        return self._evaluate_results(story, results, query)

    def _evaluate_results(self, story, results: list[dict], query: str) -> VerificationResult:
        seen_domains: set[str] = set()
        matches: list[SourceMatch] = []

        own_domain = _domain_from_url(story.url)
        if own_domain:
            tier = _classify_domain(own_domain)
            if tier <= 2:
                seen_domains.add(own_domain)
                matches.append(SourceMatch(url=story.url, domain=own_domain, title=story.title, credibility_tier=tier))

        for result in results:
            url    = result.get("url", "")
            domain = _domain_from_url(url)
            if not domain or domain in seen_domains:
                continue
            tier = _classify_domain(domain)
            if tier <= 2:
                seen_domains.add(domain)
                matches.append(SourceMatch(url=url, domain=domain, title=result.get("name", ""), credibility_tier=tier))

        source_count = len(matches)
        tier1_count  = sum(1 for m in matches if m.credibility_tier == 1)
        score        = min(100, tier1_count * 25 + (source_count - tier1_count) * 10 + story.credibility_score // 4)

        logger.info(f"  Story {story.id}: {source_count} sources ({tier1_count} Tier 1), score {score}")

        if source_count >= self.settings.min_verification_sources:
            return VerificationResult(
                story_id=story.id, status=VerificationStatus.VERIFIED,
                source_count=source_count, sources_found=matches,
                credibility_score=score, search_query_used=query,
            )

        return VerificationResult(
            story_id=story.id, status=VerificationStatus.INSUFFICIENT_SOURCES,
            source_count=source_count, sources_found=matches,
            credibility_score=score, search_query_used=query,
            rejection_reason=(
                f"Only {source_count} credible source(s) found; "
                f"minimum required: {self.settings.min_verification_sources}"
            ),
        )

    def _verify_with_fallback(self, story) -> VerificationResult:
        if not self._fallback_warned:
            logger.warning(
                "No BING_SEARCH_API_KEY — using credibility-score fallback. "
                "Add BING_SEARCH_API_KEY to .env for full 3-source verification."
            )
            self._fallback_warned = True

        score      = story.credibility_score
        own_domain = _domain_from_url(story.url)
        own_match  = SourceMatch(url=story.url, domain=own_domain, title=story.title,
                                 credibility_tier=_classify_domain(own_domain))

        if score >= self.settings.credibility_threshold:
            return VerificationResult(
                story_id=story.id, status=VerificationStatus.VERIFIED,
                source_count=1, sources_found=[own_match],
                credibility_score=score, search_query_used="(fallback)",
            )

        return VerificationResult(
            story_id=story.id, status=VerificationStatus.LOW_CREDIBILITY,
            source_count=1, sources_found=[own_match],
            credibility_score=score,
            rejection_reason=f"Credibility score {score} below threshold {self.settings.credibility_threshold}",
            search_query_used="(fallback)",
        )

    def check_batch(self, stories: list) -> list[VerificationResult]:
        results = []
        for story in stories:
            result = self.check(story)
            results.append(result)
            label = "PASS" if result.status == VerificationStatus.VERIFIED else "FAIL"
            logger.info(f"[{label}] Story {story.id}: {result.source_count} sources, score={result.credibility_score}")
        return results
