"""User lifecycle and privacy endpoints (M7)."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.services.user_lifecycle_service import UserLifecycleService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/export", response_model=dict[str, Any])
async def export_my_data(
    current_user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    """Export complete user data archive in structured JSON format (M7/GDPR)."""
    return await UserLifecycleService.export_user_data(
        user=current_user,
        session=session,
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    current_user: CurrentUser,
    session: DbSession,
) -> None:
    """Permanently delete user account and all associated personal data."""
    await UserLifecycleService.delete_user_account(
        user=current_user,
        session=session,
    )
