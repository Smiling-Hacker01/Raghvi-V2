"""Automatic memory extractor.

Extracts personal facts, preferences, and details from chat messages
using the LLM — fully dynamic, no hardcoded patterns.

Design principles:
- LLM understands natural language variations ("just relocated", "my gig is", etc.)
- Falls back silently to [] on any LLM/parse failure — chat is NEVER blocked
- Deduplication against existing memories before persisting
"""

import json
import logging
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory
from app.services.ai.client import get_ai_client
from app.services.memory.service import MemoryService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------
# Low temperature (0.0) → deterministic, structured JSON output.
# max_tokens=200 → fast, cheap, only a small array is expected.
_EXTRACTION_SYSTEM_PROMPT = """\
You are a personal fact extractor. Your ONLY job is to pull explicit personal \
facts from the user's message.

Rules:
- Only extract facts the user explicitly states about THEMSELVES.
- Never infer, assume, or fabricate anything.
- Each fact must be concise (≤ 10 words).
- Use third-person format:
    "Lives in <city>", "Works as a <role>", "Works at <company>",
    "Learning <skill>", "Loves <hobby>", "Has a dog named <name>",
    "Favorite <category> is <value>", etc.
- Only include personal facts: location, job, hobbies, family, pets, skills,
  preferences, life events.
- Return ONLY a valid JSON array of strings — no explanation, no markdown.
- If there are NO personal facts, return exactly: []

Examples
--------
Message: "I just moved to Bangalore for a new ML job at Flipkart!"
Output:  ["Lives in Bangalore", "Works in Machine Learning", "Works at Flipkart"]

Message: "What's 2 + 2?"
Output:  []

Message: "I love hiking and my dog Max comes with me every time."
Output:  ["Loves hiking", "Has a dog named Max"]

Message: "Been coding in Rust for about a year, it's wild."
Output:  ["Learning Rust"]
"""


class MemoryExtractor:
    """Extracts personal facts from user chat messages using the LLM.

    Features:
    - Fully dynamic extraction via LLM (no hardcoded patterns)
    - Handles natural phrasing, slang, and colloquialisms
    - Defensive JSON parsing with regex fallback
    - Silent failure — never blocks chat flow
    - Deduplication against existing user memories
    """

    @classmethod
    async def extract_facts(cls, message: str) -> list[str]:
        """Dynamically extract personal facts from a user message.

        Sends the message to the LLM with a strict extraction prompt and
        parses the returned JSON array.  Returns [] on any failure.

        Args:
            message: User chat message text.

        Returns:
            List of extracted fact strings, e.g. ["Lives in Seattle", "Loves hiking"].
            Empty list if no facts found or if the LLM call fails.
        """
        if not message or not message.strip():
            return []

        try:
            client = get_ai_client()
            response_text, _, _ = await client.send_message(
                messages=[{"role": "user", "content": message}],
                system_prompt=_EXTRACTION_SYSTEM_PROMPT,
                max_tokens=200,
                temperature=0.0,
            )
            return cls._parse_facts(response_text)

        except Exception as exc:
            # Never let extraction errors surface to the caller.
            # Chat delivery is more important than memory extraction.
            logger.warning(f"LLM memory extraction failed (will skip): {exc}")
            return []

    @classmethod
    def _parse_facts(cls, raw_response: str) -> list[str]:
        """Parse the LLM's raw text into a clean list of fact strings.

        The LLM is instructed to return only a JSON array, but we do
        defensive parsing — extract the first ``[...]`` block found in
        the response so minor preambles/postambles don't break things.

        Args:
            raw_response: Raw text from the LLM.

        Returns:
            List of non-empty fact strings.  Empty list on any parse error.
        """
        text = raw_response.strip()

        # Find the first JSON array in the response
        match = re.search(r"\[.*?\]", text, re.DOTALL)
        if not match:
            logger.debug(
                f"No JSON array found in extraction response: {text[:120]!r}"
            )
            return []

        try:
            facts = json.loads(match.group())
        except json.JSONDecodeError as exc:
            logger.debug(
                f"Failed to parse extraction JSON: {exc}. "
                f"Raw snippet: {text[:120]!r}"
            )
            return []

        if not isinstance(facts, list):
            return []

        # Clean and filter
        cleaned: list[str] = []
        for fact in facts:
            if not isinstance(fact, str):
                continue
            fact = fact.strip()
            if len(fact) >= 3:  # Discard empty / single-char noise
                cleaned.append(fact)

        return cleaned

    @classmethod
    async def extract_and_save_memories(
        cls,
        user_id: str,
        message: str,
        session: AsyncSession,
    ) -> list[Memory]:
        """Extract facts from a message and persist new ones to the DB.

        Skips facts that are already stored (exact-match deduplication,
        case-insensitive).

        Args:
            user_id: User's UUID string.
            message: Chat message text.
            session: Database session.

        Returns:
            List of newly created Memory instances.
        """
        candidate_facts = await cls.extract_facts(message)
        if not candidate_facts:
            return []

        # Load existing memories for deduplication
        existing_approved = await MemoryService.get_approved_memories(
            user_id=user_id,
            limit=500,
            session=session,
        )
        existing_pending = await MemoryService.get_pending_memories(
            user_id=user_id,
            session=session,
        )
        existing_contents: set[str] = {
            m.content.lower().strip()
            for m in (existing_approved + existing_pending)
        }

        created_memories: list[Memory] = []

        for fact in candidate_facts:
            fact_lower = fact.lower().strip()

            if fact_lower in existing_contents:
                logger.debug(
                    f"Skipping duplicate memory for user {user_id}: '{fact}'"
                )
                continue

            try:
                memory, is_approved, _ = await MemoryService.create_memory(
                    user_id=user_id,
                    content=fact,
                    session=session,
                )
                existing_contents.add(fact_lower)
                created_memories.append(memory)
                logger.info(
                    f"Auto-extracted memory for user {user_id}: '{fact}' "
                    f"(auto_approved={is_approved})"
                )
            except ValueError as exc:
                logger.warning(
                    f"Could not save auto-extracted memory '{fact}': {exc}"
                )

        return created_memories


def get_memory_extractor() -> type[MemoryExtractor]:
    """Return the MemoryExtractor class (used for DI / testing)."""
    return MemoryExtractor
