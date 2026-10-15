"""Data models and typed contracts for Web Research Service."""

from dataclasses import dataclass, field


@dataclass
class Citation:
    """Individual citation for a verified web source."""

    id: int
    title: str
    url: str
    snippet: str
    published_date: str | None = None


@dataclass
class SearchResult:
    """Raw result item returned from a search provider."""

    title: str
    url: str
    snippet: str
    source_name: str = ""
    relevance_score: float = 1.0


@dataclass
class ResearchRequest:
    """Typed request for performing web research."""

    query: str
    max_results: int = 5
    require_recent: bool = False
    timeout_seconds: float = 10.0


@dataclass
class ResearchResponse:
    """Synthesized research result with citations and trustworthiness metadata."""

    query: str
    performed_search: bool
    results: list[SearchResult] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    synthesized_context: str = ""
    has_conflicts: bool = False
    uncertainty_detected: bool = False
    provider_used: str = "mock"
    error_message: str | None = None
