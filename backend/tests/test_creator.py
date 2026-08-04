"""Unit tests for creator profile endpoints, story generator, and seeding."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.creator_seed import seed_creator_profile
from app.services.creator_story import CreatorStoryGenerator


@pytest.mark.asyncio
async def test_seed_creator_profile(test_db):
    """Test seeding creator profile into database."""
    async with test_db() as session:
        profile = await seed_creator_profile(session)
        assert profile is not None
        assert profile.id == "1"
        assert profile.name == "Vishal Singh Kushwaha"
        assert profile.girlfriend_name == "Disha Saini"
        assert profile.github_url == "https://github.com/Smiling-Hacker01"


@pytest.mark.asyncio
async def test_creator_story_generator(test_db):
    """Test generating creator story."""
    async with test_db() as session:
        # Ensure seeded
        await seed_creator_profile(session)

        generator = CreatorStoryGenerator()

        # Test fallback template generation directly
        profile = await generator.get_creator_profile(session)
        fallback_story = generator._generate_origin_story(profile, "poetic")
        assert "Vishal" in fallback_story or "father" in fallback_story
        assert "Disha Saini" in fallback_story
        assert "Kush" in fallback_story

        # Test generate_story with mocked AIClient
        mock_ai = MagicMock()
        mock_ai.send_message = AsyncMock(
            return_value=("Story about Vishal and Disha Saini, descendant of Kush.", 10, "mock")
        )
        with patch("app.services.ai.client.get_ai_client", return_value=mock_ai):
            story = await generator.generate_story(
                user_messages=["tell me a story"],
                user_name="Friend",
                session=session,
            )
            assert "Vishal" in story
