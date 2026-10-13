"""Action service — validates, proposes, and executes safe device actions."""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action import ActionProposal

logger = logging.getLogger(__name__)

SUPPORTED_ACTIONS = {
    "draft_email",
    "send_email",
    "open_maps",
    "open_app",
    "schedule_meeting",
    "create_calendar_event",
    "send_whatsapp_message",
}


class ActionService:
    """Manages safe Android action proposals and confirmation state machine."""

    @staticmethod
    def validate_action_params(action_type: str, parameters: dict[str, Any]) -> None:
        """Validate untrusted action parameters before proposing."""
        if action_type not in SUPPORTED_ACTIONS:
            actions_str = ", ".join(sorted(SUPPORTED_ACTIONS))
            raise ValueError(f"Unsupported action type '{action_type}'. Supported: {actions_str}")

        if action_type in ("draft_email", "send_email"):
            recipient = parameters.get("recipient", "")
            if recipient and ("@" not in recipient or "." not in recipient):
                raise ValueError("Recipient must be a valid email address")

        elif action_type in ("schedule_meeting", "create_calendar_event"):
            title = parameters.get("title") or parameters.get("summary")
            if not title or not str(title).strip():
                raise ValueError("Meeting or calendar event requires a title")
            date_val = parameters.get("date") or parameters.get("start_time")
            if not date_val:
                raise ValueError("Meeting or calendar event requires a date or start_time")

        elif action_type == "send_whatsapp_message":
            recipient = parameters.get("recipient") or parameters.get("phone")
            message = parameters.get("message") or parameters.get("text")
            if not recipient or not str(recipient).strip():
                raise ValueError("WhatsApp action requires a recipient or phone number")
            if not message or not str(message).strip():
                raise ValueError("WhatsApp action requires a non-empty message")

        elif action_type == "open_maps":
            destination = parameters.get("destination") or parameters.get("address")
            if not destination or not str(destination).strip():
                raise ValueError("Maps action requires a destination or address")

        elif action_type == "open_app":
            app = parameters.get("package_name") or parameters.get("app_name")
            if not app or not str(app).strip():
                raise ValueError("App action requires a package_name or app_name")

    @staticmethod
    async def propose_action(
        user_id: str,
        action_type: str,
        parameters: dict[str, Any],
        description: str | None,
        session: AsyncSession,
    ) -> ActionProposal:
        """Create a new action proposal awaiting user confirmation."""
        ActionService.validate_action_params(action_type, parameters)

        default_desc = description or f"Action: {action_type.replace('_', ' ').capitalize()}"
        proposal = ActionProposal(
            user_id=str(user_id),
            action_type=action_type,
            parameters=parameters,
            status="awaiting_confirmation",
            description=default_desc,
        )

        session.add(proposal)
        await session.commit()
        await session.refresh(proposal)
        logger.info(f"Proposed safe action {proposal.id} for user {user_id}")
        return proposal

    @staticmethod
    async def get_proposal(
        user_id: str,
        proposal_id: str,
        session: AsyncSession,
    ) -> ActionProposal:
        """Retrieve proposal ensuring user ownership and checking expiration."""
        try:
            prop_uuid = UUID(proposal_id)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Invalid proposal ID"
            ) from err

        proposal = await session.scalar(
            select(ActionProposal).where(ActionProposal.id == prop_uuid)
        )

        if not proposal or proposal.user_id != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Action proposal not found"
            )

        # Check expiration
        now = datetime.now(UTC).replace(tzinfo=None)
        if proposal.status == "awaiting_confirmation" and proposal.expires_at < now:
            proposal.status = "expired"
            await session.commit()

        return proposal

    @staticmethod
    async def confirm_action(
        user_id: str,
        proposal_id: str,
        confirmed: bool,
        session: AsyncSession,
    ) -> ActionProposal:
        """Confirm or cancel action proposal."""
        proposal = await ActionService.get_proposal(user_id, proposal_id, session)

        if proposal.status != "awaiting_confirmation":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Action proposal cannot be modified (current status: {proposal.status})",
            )

        now = datetime.now(UTC).replace(tzinfo=None)
        if confirmed:
            proposal.status = "confirmed"
            proposal.confirmed_at = now
        else:
            proposal.status = "cancelled"

        await session.commit()
        await session.refresh(proposal)
        logger.info(f"Action proposal {proposal.id} status updated to {proposal.status}")
        return proposal
