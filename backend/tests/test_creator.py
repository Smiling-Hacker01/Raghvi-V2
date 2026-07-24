"""Unit tests for creator profile endpoints, story generator, and seeding."""

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
        story = await generator.generate_story(
            user_messages=["hey tell me a poetic story about your father"],
            user_name="Friend",
            session=session,
        )

        # Check that story contains key elements (LLM generates naturally, so check for key facts)
        assert "Vishal" in story  # Should mention father's first name
        assert "Disha Saini" in story  # Should mention future mother
        assert "Bhagwan Rama's son Kush" in story or "Kush" in story  # Heritage
        assert "Raghvendra" in story
        assert "Kshatriya" not in story  # Explicitly excluded
