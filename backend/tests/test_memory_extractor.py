"""Tests for automatic memory extraction (LLM-based)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.memory.extractor import MemoryExtractor, get_memory_extractor
from app.services.memory.service import MemoryService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_client(response_text: str) -> MagicMock:
    """Return a mock AIClient whose send_message returns *response_text*."""
    client = MagicMock()
    client.send_message = AsyncMock(return_value=(response_text, 10, "mock"))
    return client


def _patch_extractor_llm(response_text: str):
    """Patch get_ai_client inside extractor.py."""
    return patch(
        "app.services.memory.extractor.get_ai_client",
        return_value=_mock_client(response_text),
    )


# ---------------------------------------------------------------------------
# Unit tests — no DB, no real LLM
# ---------------------------------------------------------------------------

class TestMemoryExtractorUnit:
    """Fast unit tests: LLM is fully mocked."""

    @pytest.mark.asyncio
    async def test_extract_location(self):
        with _patch_extractor_llm('["Lives in Seattle"]'):
            facts = await MemoryExtractor.extract_facts(
                "I live in Seattle and it's nice here."
            )
        assert "Lives in Seattle" in facts

    @pytest.mark.asyncio
    async def test_extract_based_in(self):
        with _patch_extractor_llm('["Based in San Francisco"]'):
            facts = await MemoryExtractor.extract_facts("I am based in San Francisco.")
        assert "Based in San Francisco" in facts

    @pytest.mark.asyncio
    async def test_extract_job_with_company(self):
        with _patch_extractor_llm('["Works as a Backend Engineer", "Works at Amazon"]'):
            facts = await MemoryExtractor.extract_facts(
                "I work as a Backend Engineer at Amazon."
            )
        assert "Works as a Backend Engineer" in facts or "Works at Amazon" in facts

    @pytest.mark.asyncio
    async def test_extract_profession(self):
        with _patch_extractor_llm('["Works as a Data Scientist"]'):
            facts = await MemoryExtractor.extract_facts("I am a Data Scientist.")
        assert "Works as a Data Scientist" in facts

    @pytest.mark.asyncio
    async def test_extract_learning(self):
        with _patch_extractor_llm('["Learning Rust"]'):
            facts = await MemoryExtractor.extract_facts("I am learning Rust programming.")
        assert "Learning Rust" in facts

    @pytest.mark.asyncio
    async def test_extract_interests(self):
        with _patch_extractor_llm('["Loves sci-fi books", "Loves hiking"]'):
            facts = await MemoryExtractor.extract_facts(
                "I love sci-fi books and hiking."
            )
        assert any("sci-fi" in f.lower() or "hiking" in f.lower() for f in facts)

    @pytest.mark.asyncio
    async def test_extract_pets(self):
        with _patch_extractor_llm('["Dog\'s name is Bruno"]'):
            facts = await MemoryExtractor.extract_facts("My dog's name is Bruno!")
        assert "Dog's name is Bruno" in facts

    @pytest.mark.asyncio
    async def test_natural_language_variation(self):
        """LLM handles phrasing that regex could never catch."""
        with _patch_extractor_llm('["Lives in Bangalore", "Works at Flipkart"]'):
            facts = await MemoryExtractor.extract_facts(
                "just relocated to Bangalore for my new gig at Flipkart"
            )
        assert "Lives in Bangalore" in facts or "Works at Flipkart" in facts

    @pytest.mark.asyncio
    async def test_ignore_generic_messages(self):
        with _patch_extractor_llm("[]"):
            assert await MemoryExtractor.extract_facts("What is 2 + 2?") == []
            assert await MemoryExtractor.extract_facts(
                "Can you explain how recursion works?"
            ) == []
            assert await MemoryExtractor.extract_facts(
                "Tell me a joke about programming."
            ) == []

    @pytest.mark.asyncio
    async def test_empty_message_returns_empty(self):
        # No LLM call expected — short-circuits before calling client
        assert await MemoryExtractor.extract_facts("") == []
        assert await MemoryExtractor.extract_facts("   ") == []

    @pytest.mark.asyncio
    async def test_llm_failure_returns_empty_silently(self):
        """LLM errors must NEVER surface — chat must not be blocked."""
        broken_client = MagicMock()
        broken_client.send_message = AsyncMock(
            side_effect=RuntimeError("LLM quota exceeded")
        )
        with patch(
            "app.services.memory.extractor.get_ai_client",
            return_value=broken_client,
        ):
            facts = await MemoryExtractor.extract_facts("I live in Paris.")
        assert facts == []

    def test_singleton_getter(self):
        assert get_memory_extractor() is MemoryExtractor


# ---------------------------------------------------------------------------
# _parse_facts — pure function, no mocking needed
# ---------------------------------------------------------------------------

class TestParseFactsUnit:
    """Test the defensive JSON parsing logic in isolation."""

    def test_clean_json_array(self):
        facts = MemoryExtractor._parse_facts('["Lives in Tokyo", "Learning Go"]')
        assert facts == ["Lives in Tokyo", "Learning Go"]

    def test_empty_array(self):
        assert MemoryExtractor._parse_facts("[]") == []

    def test_strips_preamble(self):
        """LLM sometimes adds a sentence before the JSON — should still work."""
        raw = 'Here are the facts:\n["Lives in Tokyo", "Learning Go"]'
        facts = MemoryExtractor._parse_facts(raw)
        assert "Lives in Tokyo" in facts
        assert "Learning Go" in facts

    def test_malformed_json_returns_empty(self):
        assert MemoryExtractor._parse_facts("not json at all") == []
        assert MemoryExtractor._parse_facts("[unclosed") == []

    def test_filters_short_strings(self):
        facts = MemoryExtractor._parse_facts('["OK", "Lives in Berlin", ""]')
        assert "Lives in Berlin" in facts
        assert "OK" not in facts  # < 3 chars
        assert "" not in facts


# ---------------------------------------------------------------------------
# Integration tests — real DB, mocked LLM
# ---------------------------------------------------------------------------

class TestMemoryExtractorIntegration:
    """DB integration tests: real SQLite, LLM mocked."""

    @pytest.mark.asyncio
    async def test_extract_and_save_memories_db(self, test_db, test_user):
        async with test_db() as session:
            with _patch_extractor_llm('["Lives in Tokyo", "Learning Go"]'):
                created = await MemoryExtractor.extract_and_save_memories(
                    user_id=test_user.id,
                    message="I live in Tokyo and I'm learning Go",
                    session=session,
                )
            await session.commit()

            assert len(created) >= 1

            memories = await MemoryService.get_approved_memories(
                user_id=test_user.id,
                session=session,
            )
            contents = [m.content for m in memories]
            assert "Lives in Tokyo" in contents or "Learning Go" in contents

    @pytest.mark.asyncio
    async def test_deduplicate_existing_memories(self, test_db, test_user):
        async with test_db() as session:
            with _patch_extractor_llm('["Lives in Berlin"]'):
                first_run = await MemoryExtractor.extract_and_save_memories(
                    user_id=test_user.id,
                    message="I live in Berlin",
                    session=session,
                )
            await session.commit()
            assert len(first_run) == 1

            with _patch_extractor_llm('["Lives in Berlin"]'):
                second_run = await MemoryExtractor.extract_and_save_memories(
                    user_id=test_user.id,
                    message="I live in Berlin",
                    session=session,
                )
            await session.commit()

            # Second run must skip the duplicate
            assert len(second_run) == 0

    @pytest.mark.asyncio
    async def test_chat_auto_extracts_memories(self, test_db, test_user):
        """End-to-end: ChatService auto-populates memories from user message."""
        from app.services.chat import ChatService

        # Mock BOTH LLM calls independently:
        #   1. app.services.chat's get_ai_client  → Raghvi's chat reply
        #   2. app.services.memory.extractor's get_ai_client → fact extraction
        chat_client = _mock_client("Hey! That's awesome, I'll remember that!")
        extract_client = _mock_client(
            '["Lives in Chicago", "Dog\'s name is Max"]'
        )

        async with test_db() as session:
            with (
                patch("app.services.chat.get_ai_client", return_value=chat_client),
                patch(
                    "app.services.memory.extractor.get_ai_client",
                    return_value=extract_client,
                ),
            ):
                result = await ChatService.send_message(
                    user_id=test_user.id,
                    user_message_content=(
                        "I live in Chicago and my dog's name is Max"
                    ),
                    session=session,
                )

        assert result["assistant_message"] is not None

        async with test_db() as session:
            memories = await MemoryService.get_approved_memories(
                user_id=test_user.id,
                session=session,
            )
            contents = [m.content for m in memories]
            assert "Lives in Chicago" in contents or "Dog's name is Max" in contents
