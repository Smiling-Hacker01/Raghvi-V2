"""Web search provider adapters with fallback and mocking capabilities."""

import abc
import logging
from urllib.parse import quote_plus

import httpx

from app.services.research.models import SearchResult
from app.services.research.security import sanitize_web_content, validate_url

logger = logging.getLogger(__name__)


class SearchProvider(abc.ABC):
    """Abstract interface for all web search providers."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Provider identifier name."""
        pass

    @abc.abstractmethod
    async def search(
        self, query: str, max_results: int = 5, timeout_seconds: float = 10.0
    ) -> list[SearchResult]:
        """Perform search query and return raw results.

        Args:
            query: User search query
            max_results: Max items to return
            timeout_seconds: Maximum request duration in seconds

        Returns:
            List of SearchResult objects
        """
        pass


class MockSearchProvider(SearchProvider):
    """Deterministic mock search provider for unit testing and offline development."""

    def __init__(
        self,
        canned_results: list[SearchResult] | None = None,
        simulate_error: Exception | None = None,
    ):
        self._canned_results = canned_results
        self._simulate_error = simulate_error
        self.recorded_queries: list[str] = []

    @property
    def name(self) -> str:
        return "mock"

    async def search(
        self, query: str, max_results: int = 5, timeout_seconds: float = 10.0
    ) -> list[SearchResult]:
        self.recorded_queries.append(query)
        if self._simulate_error:
            raise self._simulate_error

        if self._canned_results is not None:
            return self._canned_results[:max_results]

        # Default deterministic mock responses for test queries
        return [
            SearchResult(
                title=f"Result 1 for {query}",
                url="https://en.wikipedia.org/wiki/Artificial_intelligence",
                snippet=f"Documentation and factual context regarding {query}.",
                source_name="Wikipedia",
                relevance_score=0.95,
            ),
            SearchResult(
                title=f"Result 2 for {query}",
                url="https://news.ycombinator.com/item?id=12345",
                snippet=f"Technical updates concerning {query}.",
                source_name="Hacker News",
                relevance_score=0.88,
            ),
        ][:max_results]


class DuckDuckGoSearchProvider(SearchProvider):
    """Zero-credential web search provider utilizing DuckDuckGo API/HTML endpoints."""

    @property
    def name(self) -> str:
        return "duckduckgo"

    async def search(
        self, query: str, max_results: int = 5, timeout_seconds: float = 10.0
    ) -> list[SearchResult]:
        encoded_query = quote_plus(query)
        url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1&skip_disambig=1"

        try:
            async with httpx.AsyncClient(
                timeout=timeout_seconds,
                headers={"User-Agent": "Raghvi-Assistant/2.0"},
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    logger.warning("DuckDuckGo returned HTTP %d", response.status_code)
                    return []

                data = response.json()
                results: list[SearchResult] = []

                # 1. Check primary abstract
                if data.get("AbstractText") and data.get("AbstractURL"):
                    target_url = data["AbstractURL"]
                    try:
                        validate_url(target_url)
                        results.append(
                            SearchResult(
                                title=data.get("Heading") or query,
                                url=target_url,
                                snippet=sanitize_web_content(data["AbstractText"]),
                                source_name=data.get("AbstractSource") or "DuckDuckGo",
                                relevance_score=1.0,
                            )
                        )
                    except Exception as exc:
                        logger.warning("Skipping untrusted URL %s: %s", target_url, exc)

                # 2. Check Related Topics
                for topic in data.get("RelatedTopics", []):
                    if len(results) >= max_results:
                        break
                    topic_url = topic.get("FirstURL")
                    text = topic.get("Text")
                    if topic_url and text:
                        try:
                            validate_url(topic_url)
                            results.append(
                                SearchResult(
                                    title=text.split(" - ")[0] if " - " in text else query,
                                    url=topic_url,
                                    snippet=sanitize_web_content(text),
                                    source_name="DuckDuckGo",
                                    relevance_score=0.85,
                                )
                            )
                        except Exception as exc:
                            logger.warning("Skipping untrusted URL %s: %s", topic_url, exc)

                return results

        except Exception as exc:
            logger.error("DuckDuckGo search failed for '%s': %s", query, exc)
            return []
