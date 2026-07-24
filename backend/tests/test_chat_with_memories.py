"""Integration tests for chat with memory context."""

import pytest

from app.models.user import User
from app.security.password import hash_password
from app.services.ai.prompt import build_system_prompt
from app.services.memory.retrieval import get_retriever
from app.services.memory.service import MemoryService


class TestChatWithMemories:
    """Integration tests for chat with memory retrieval."""

    @pytest.fixture
    async def user(self, test_db):
        """Create a test user."""
        async with test_db() as session:
            user = User(
                id="550e8400-e29b-41d4-a716-446655440000",
                username="chattest",
                email="chattest@example.com",
                password_hash=hash_password("TestPassword123"),
                name="Chat Test User",
                phone="1234567890",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    @pytest.mark.asyncio
    async def test_chat_with_memory_context(self, test_db, user):
        """Test that chat includes memory context in system prompt."""
        async with test_db() as session:
            # Create memories
            await MemoryService.create_memory(
                user_id=user.id,
                content="I'm learning Rust programming",
                session=session,
            )
            await MemoryService.create_memory(
                user_id=user.id,
                content="I work as a backend engineer",
                session=session,
            )

            # Get memories
            memories = await MemoryService.get_approved_memories(
                user_id=user.id,
                session=session,
            )

            assert len(memories) == 2

            # Build system prompt with memories (await async function)
            prompt = await build_system_prompt(memories, session)

            # Verify memory context is in prompt
            assert "learning rust" in prompt.lower()
            assert "backend engineer" in prompt.lower()

    @pytest.mark.asyncio
    async def test_system_prompt_without_memories(self):
        """Test system prompt when user has no memories."""
        prompt = await build_system_prompt(None, None)

        # Should have core personality
        assert "Raghvi" in prompt
        assert "friend" in prompt.lower()

    @pytest.mark.asyncio
    async def test_chat_retrieves_relevant_memories(self, test_db, user):
        """Test that chat retrieval uses relevant memories."""
        async with test_db() as session:
            # Create memories
            await MemoryService.create_memory(
                user_id=user.id,
                content="I'm learning Python and Rust",
                session=session,
            )
            await MemoryService.create_memory(
                user_id=user.id,
                content="I love hiking in nature",
                session=session,
            )

            await session.commit()

            # Retrieve using chat query
            retriever = get_retriever()
            results = await retriever.retrieve(
                user_id=user.id,
                query="How do I learn Rust better?",
                session=session,
            )

            # Should find the Rust memory (most relevant)
            assert len(results) > 0
            assert "Rust" in results[0].content
