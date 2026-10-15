"""Action proposal endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.actions import (
    ActionConfirmationRequest,
    ActionProposalRequest,
    ActionProposalResponse,
)
from app.services.action_service import ActionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/actions", tags=["actions"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("", response_model=list[ActionProposalResponse])
async def list_actions(
    current_user: CurrentUser,
    session: DbSession,
    status_filter: Annotated[
        str | None,
        Query(
            alias="status",
            description="Filter: awaiting_confirmation, confirmed, cancelled, expired",
        ),
    ] = None,
) -> list[ActionProposalResponse]:
    """List action proposals for the current user."""
    proposals = await ActionService.list_proposals(
        user_id=str(current_user.id),
        status_filter=status_filter,
        session=session,
    )
    return [
        ActionProposalResponse(
            id=str(p.id),
            user_id=p.user_id,
            action_type=p.action_type,
            parameters=p.parameters,
            status=p.status,
            description=p.description,
            expires_at=p.expires_at.isoformat(),
            created_at=p.created_at.isoformat(),
            confirmed_at=p.confirmed_at.isoformat() if p.confirmed_at else None,
        )
        for p in proposals
    ]


@router.post("/propose", response_model=ActionProposalResponse, status_code=status.HTTP_201_CREATED)
async def propose_action(
    request: ActionProposalRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> ActionProposalResponse:
    """Propose a device action awaiting user confirmation."""
    try:
        proposal = await ActionService.propose_action(
            user_id=str(current_user.id),
            action_type=request.action_type,
            parameters=request.parameters,
            description=request.description,
            session=session,
        )
        return ActionProposalResponse(
            id=str(proposal.id),
            user_id=proposal.user_id,
            action_type=proposal.action_type,
            parameters=proposal.parameters,
            status=proposal.status,
            description=proposal.description,
            expires_at=proposal.expires_at.isoformat(),
            created_at=proposal.created_at.isoformat(),
            confirmed_at=proposal.confirmed_at.isoformat() if proposal.confirmed_at else None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e


@router.get("/{proposal_id}", response_model=ActionProposalResponse)
async def get_proposal(
    proposal_id: str,
    current_user: CurrentUser,
    session: DbSession,
) -> ActionProposalResponse:
    """Get action proposal details."""
    proposal = await ActionService.get_proposal(
        user_id=str(current_user.id),
        proposal_id=proposal_id,
        session=session,
    )
    return ActionProposalResponse(
        id=str(proposal.id),
        user_id=proposal.user_id,
        action_type=proposal.action_type,
        parameters=proposal.parameters,
        status=proposal.status,
        description=proposal.description,
        expires_at=proposal.expires_at.isoformat(),
        created_at=proposal.created_at.isoformat(),
        confirmed_at=proposal.confirmed_at.isoformat() if proposal.confirmed_at else None,
    )


@router.post("/{proposal_id}/confirm", response_model=ActionProposalResponse)
async def confirm_action(
    proposal_id: str,
    request: ActionConfirmationRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> ActionProposalResponse:
    """Confirm or cancel an action proposal."""
    proposal = await ActionService.confirm_action(
        user_id=str(current_user.id),
        proposal_id=proposal_id,
        confirmed=request.confirmed,
        session=session,
    )
    return ActionProposalResponse(
        id=str(proposal.id),
        user_id=proposal.user_id,
        action_type=proposal.action_type,
        parameters=proposal.parameters,
        status=proposal.status,
        description=proposal.description,
        expires_at=proposal.expires_at.isoformat(),
        created_at=proposal.created_at.isoformat(),
        confirmed_at=proposal.confirmed_at.isoformat() if proposal.confirmed_at else None,
    )
