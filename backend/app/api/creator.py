"""Endpoints for creator information and stories."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.creator import (
    CreatorProfileResponse,
    CreatorStoryRequest,
    CreatorStoryResponse,
)
from app.services.creator_story import get_story_generator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/creator", tags=["creator"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/profile", response_model=CreatorProfileResponse)
async def get_creator_profile(
    session: DbSession,
) -> CreatorProfileResponse:
    """Get Raghvi's creator profile."""
    try:
        generator = get_story_generator()
        profile = await generator.get_creator_profile(session)

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Creator profile not found",
            )

        return CreatorProfileResponse(
            name=profile.name,
            father_name=profile.father_name,
            mother_name=profile.mother_name,
            girlfriend_name=profile.girlfriend_name,
            birthplace=profile.birthplace,
            hometown=profile.hometown,
            education_background=profile.education_background,
            graduation_year=profile.graduation_year,
            graduation_degree=profile.graduation_degree,
            hobbies=profile.hobbies,
            dreams=profile.dreams,
            linkedin_url=profile.linkedin_url,
            github_url=profile.github_url,
            instagram_url=profile.instagram_url,
        )

    except Exception as e:
        logger.error(f"Failed to get creator profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load creator profile",
        ) from e


@router.post("/story", response_model=CreatorStoryResponse)
async def generate_creator_story(
    request: CreatorStoryRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> CreatorStoryResponse:
    """Generate a dynamic creator story.

    This endpoint generates different stories each time,
    personalized to the user's communication style.
    """
    try:
        generator = get_story_generator()

        # Get recent user messages for tone analysis
        # (In a real app, you'd fetch from chat history)
        user_messages = [request.user_tone or ""]

        # Generate story
        story = await generator.generate_story(
            user_messages=user_messages,
            user_name=current_user.name,
            session=session,
        )

        return CreatorStoryResponse(
            story=story,
            tone=request.user_tone or "warm",
        )

    except Exception as e:
        logger.error(f"Failed to generate creator story: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate story",
        ) from e
