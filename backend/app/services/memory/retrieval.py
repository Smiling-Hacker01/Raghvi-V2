"""Semantic memory retrieval using TF-IDF similarity.

Retrieves relevant approved memories for chat context.
"""

import logging
import re
from collections import Counter
from math import log

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory
from app.services.memory.service import MemoryService

logger = logging.getLogger(__name__)


class TFIDFRetriever:
    """TF-IDF based semantic memory retrieval.

    Features:
    - Fast similarity scoring (no ML models)
    - Configurable top-K retrieval
    - Stopword filtering (common words ignored)
    - Case-insensitive matching

    Algorithm:
    1. Tokenize query and memories
    2. Calculate TF (term frequency) for each
    3. Calculate IDF (inverse document frequency)
    4. Score: TF-IDF similarity
    5. Return top K most relevant
    """

    # Common English words to ignore
    STOPWORDS = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "have",
        "has",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "my",
        "your",
        "his",
        "her",
        "its",
        "our",
        "their",
        "this",
        "that",
        "these",
        "those",
        "what",
        "which",
        "who",
        "when",
        "where",
        "why",
        "how",
        "not",
        "no",
        "yes",
        "can",
        "may",
    }

    def __init__(self, top_k: int = 9):
        """Initialize retriever.

        Args:
            top_k: Number of memories to retrieve (default 9 for context window)
        """
        self.top_k = min(top_k, 9)  # Cap at 9

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenize text into words.

        Args:
            text: Text to tokenize

        Returns:
            List of lowercase words (stopwords removed)
        """
        # Convert to lowercase
        text = text.lower()

        # Remove special characters, keep only alphanumeric and spaces
        text = re.sub(r"[^a-z0-9\s]", " ", text)

        # Split into words
        words = text.split()

        # Filter stopwords
        words = [w for w in words if w and w not in TFIDFRetriever.STOPWORDS]

        return words

    @staticmethod
    def _calculate_tf(tokens: list[str]) -> dict[str, float]:
        """Calculate term frequency.

        Args:
            tokens: List of tokens

        Returns:
            Dict of term -> frequency (0.0 to 1.0)
        """
        if not tokens:
            return {}

        counts = Counter(tokens)
        max_count = max(counts.values())

        # Normalize by max frequency
        tf = {term: count / max_count for term, count in counts.items()}

        return tf

    def _calculate_idf(self, documents: list[list[str]]) -> dict[str, float]:
        """Calculate inverse document frequency.

        Args:
            documents: List of tokenized documents

        Returns:
            Dict of term -> IDF score (log scale)
        """
        if not documents:
            return {}

        total_docs = len(documents)
        term_doc_count: dict[str, int] = {}

        # Count how many documents contain each term
        for doc in documents:
            for term in set(doc):  # Set to count only once per doc
                term_doc_count[term] = term_doc_count.get(term, 0) + 1

        # Calculate IDF with smoothing (+1.0)
        # Ensures matching terms in single/few docs have positive weight
        idf = {term: log(total_docs / count) + 1.0 for term, count in term_doc_count.items()}

        return idf

    def _calculate_tfidf_score(
        self,
        query_tf: dict[str, float],
        doc_tf: dict[str, float],
        idf: dict[str, float],
    ) -> float:
        """Calculate TF-IDF similarity between query and document.

        Args:
            query_tf: Query term frequencies
            doc_tf: Document term frequencies
            idf: Global IDF scores

        Returns:
            Similarity score (0.0 to 1.0+)
        """
        score = 0.0

        # Score: sum of (query_tf * doc_tf * idf) for matching terms
        for term in query_tf:
            if term in doc_tf:
                term_score = query_tf[term] * doc_tf[term] * idf.get(term, 0)
                score += term_score

        return score

    async def retrieve(
        self,
        user_id: str,
        query: str,
        session: AsyncSession,
    ) -> list[Memory]:
        """Retrieve most relevant memories for a query.

        Args:
            user_id: User's UUID
            query: Chat message or retrieval query
            session: Database session

        Returns:
            List of top-K most relevant approved memories
        """
        # Get approved memories (optimized limit)
        memories = await MemoryService.get_approved_memories(
            user_id=user_id,
            limit=70,  # Reduced from 100 for faster retrieval
            session=session,
        )

        if not memories:
            logger.debug(f"No approved memories found for user {user_id}")
            return []

        # Tokenize query
        query_tokens = self._tokenize(query)
        if not query_tokens:
            logger.debug("Query has no meaningful tokens after stopword removal")
            return []

        # Tokenize all memories
        memory_tokens_list = [self._tokenize(m.content) for m in memories]

        # Calculate TF for query
        query_tf = self._calculate_tf(query_tokens)

        # Calculate TF for each memory
        memory_tf_list = [self._calculate_tf(tokens) for tokens in memory_tokens_list]

        # Calculate global IDF
        idf = self._calculate_idf(memory_tokens_list)

        # Score each memory
        scores = []
        for memory, doc_tf in zip(memories, memory_tf_list, strict=True):
            score = self._calculate_tfidf_score(query_tf, doc_tf, idf)
            scores.append((memory, score))

        # Sort by score (highest first)
        scores.sort(key=lambda x: x[1], reverse=True)

        # Return top-K
        result = [memory for memory, score in scores[: self.top_k] if score > 0]

        top_score = scores[0][1] if scores else 0.0
        logger.info(
            f"Retrieved {len(result)} memories for user {user_id}: top_score={top_score:.3f}"
        )

        return result


def get_retriever(top_k: int = 9) -> TFIDFRetriever:
    """Get a memory retriever instance.

    Args:
        top_k: Number of memories to retrieve

    Returns:
        TFIDFRetriever instance
    """
    return TFIDFRetriever(top_k=top_k)
