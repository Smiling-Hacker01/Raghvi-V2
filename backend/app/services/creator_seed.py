"""Creator profile automatic seeding & singleton enforcement service.

Ensures that:
1. The database always has the CreatorProfile seeded automatically on startup.
2. Only ONE creator entry (Vishal Singh Kushwaha, id="1") exists across all environments.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.creator import CreatorProfile

logger = logging.getLogger(__name__)

CREATOR_DATA = {
    "id": "1",
    "name": "Vishal Singh Kushwaha",
    "father_name": "Shyam Singh",
    "mother_name": "Urmila Devi",
    "girlfriend_name": "Disha Saini",
    "family_lineage": "Descendant of Bhagwan Rama's son Kush",
    "birthplace": "Kanpur",
    "ancestral_roots": "Rajasthan",
    "hometown": "Ghaziabad",
    "education_background": "BCA Graduate (2026)",
    "graduation_year": "2026",
    "graduation_degree": "BCA",
    "personality": "Introvert, thoughtful, disciplined, independent",
    "hobbies": "Weight lifting, reading, exploring, astronomy, space, nature",
    "dreams": "Achieving greatness while building a peaceful, loving family",
    "github_url": "https://github.com/Smiling-Hacker01",
    "linkedin_url": "https://www.linkedin.com/in/sdevsk/",
    "instagram_url": "https://www.instagram.com/eccedentesiast_vsk/",
    "twitter_url": None,
    "raghvi_name_origin": (
        "Feminine form of Raghvendra, and the same special name given to future mother Disha Saini"
    ),
    "creation_purpose": "Created so that no one ever has to feel alone",
}


async def seed_creator_profile(session: AsyncSession) -> CreatorProfile:
    """Ensure the singleton creator profile exists and purge any invalid entries."""
    try:
        # Enforce singleton: Purge any non-"1" rows
        await session.execute(delete(CreatorProfile).where(CreatorProfile.id != "1"))

        # Fetch primary creator profile (id="1")
        profile = await session.scalar(select(CreatorProfile).where(CreatorProfile.id == "1"))

        now = datetime.now(UTC)
        if not profile:
            logger.info("Seeding initial CreatorProfile into database...")
            profile = CreatorProfile(
                **CREATOR_DATA,
                created_at=now,
                updated_at=now,
            )
            session.add(profile)
        else:
            # Update fields if changed
            for key, val in CREATOR_DATA.items():
                if key != "id" and getattr(profile, key) != val:
                    setattr(profile, key, val)
            profile.updated_at = now

        await session.commit()
        await session.refresh(profile)
        logger.info(f"Creator profile verified for: {profile.name}")
        return profile
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to seed creator profile: {e}")
        raise


async def ensure_creator_seeded_on_startup() -> None:
    """Startup hook to automatically seed creator profile on any environment."""
    try:
        async with AsyncSessionLocal() as session:
            await seed_creator_profile(session)
    except Exception as e:
        logger.warning(f"Creator profile startup seeding deferred: {e}")
