from dataclasses import dataclass, field
from enum import Enum


class VerificationStatus(str, Enum):
    VERIFIED             = "verified"
    INSUFFICIENT_SOURCES = "insufficient_sources"
    LOW_CREDIBILITY      = "low_credibility"
    ERROR                = "error"


@dataclass
class SourceMatch:
    """A single source URL found to corroborate a story."""
    url: str
    domain: str
    title: str
    credibility_tier: int  # 1 = Tier 1 (Reuters/AP/BBC), 2 = Tier 2, 3 = unknown


@dataclass
class VerificationResult:
    """
    Full output of the fact-check agent for one story.
    Persisted to fact_check_results and used to gate the writing stage.
    """
    story_id: int
    status: VerificationStatus
    source_count: int
    sources_found: list[SourceMatch] = field(default_factory=list)
    credibility_score: int = 0
    rejection_reason: str = ""
    search_query_used: str = ""
