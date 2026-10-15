"""Web research package providing secure search, query classification, and citations."""

from app.services.research.models import Citation, ResearchRequest, ResearchResponse, SearchResult
from app.services.research.providers import (
    DuckDuckGoSearchProvider,
    MockSearchProvider,
    SearchProvider,
)
from app.services.research.security import SecurityException, sanitize_web_content, validate_url
from app.services.research.service import ResearchService, get_research_service

__all__ = [
    "Citation",
    "DuckDuckGoSearchProvider",
    "MockSearchProvider",
    "ResearchRequest",
    "ResearchResponse",
    "ResearchService",
    "SearchResult",
    "SearchProvider",
    "SecurityException",
    "get_research_service",
    "sanitize_web_content",
    "validate_url",
]
