"""Briefing API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.briefing import BriefingPreferences, BriefingResponse
from app.services.briefing_service import BriefingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/briefings", tags=["briefings"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/today", response_model=BriefingResponse)
async def get_today_briefing(
    current_user: CurrentUser,
    session: DbSession,
) -> BriefingResponse:
    """Get today's proactive daily briefing."""
    return await BriefingService.get_daily_briefing(
        user=current_user,
        session=session,
    )


@router.get("/preferences", response_model=BriefingPreferences)
async def get_briefing_preferences(
    current_user: CurrentUser,
) -> BriefingPreferences:
    """Get briefing preferences."""
    prefs = current_user.preferences or {}
    return BriefingPreferences(
        opt_in=prefs.get("briefing_opt_in", False),
        quiet_hours_start=prefs.get("quiet_hours_start", 22),
        quiet_hours_end=prefs.get("quiet_hours_end", 7),
        morning_time=prefs.get("morning_time", "08:00"),
    )


@router.patch("/preferences", response_model=BriefingPreferences)
async def update_briefing_preferences(
    preferences: BriefingPreferences,
    current_user: CurrentUser,
    session: DbSession,
) -> BriefingPreferences:
    """Update briefing opt-in and quiet hours preferences."""
    return await BriefingService.update_preferences(
        user=current_user,
        prefs=preferences,
        session=session,
    )
