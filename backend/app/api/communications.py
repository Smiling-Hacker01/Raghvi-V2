"""Communication endpoints — emails, WhatsApp, context-aware human replies, and meetings."""

import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db_session
from app.models.communication import CommunicationItem
from app.models.user import User
from app.schemas.communication import (
    DraftReplyRequest,
    DraftReplyResponse,
    EmailItemResponse,
    ScheduleMeetingRequest,
    SeedCommunicationRequest,
    SendRealEmailRequest,
    SyncRealEmailRequest,
    WhatsAppItemResponse,
)
from app.services.communication_service import CommunicationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/communications", tags=["communications"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/emails", response_model=list[EmailItemResponse])
async def list_or_search_emails(
    current_user: CurrentUser,
    session: DbSession,
    q: Annotated[str | None, Query(description="Search keyword or subject")] = None,
    sender: Annotated[str | None, Query(description="Filter by sender name/email")] = None,
    account_id: Annotated[UUID | None, Query(description="Filter by connected account ID")] = None,
    account_label: Annotated[
        str | None, Query(description="Filter by account label (e.g. Work, Personal)")
    ] = None,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[EmailItemResponse]:
    """Check unread emails or search for specific emails by sender, topic, or connected account."""
    items = await CommunicationService.get_emails(
        user_id=str(current_user.id),
        query=q,
        sender_query=sender,
        account_id=account_id,
        account_label_query=account_label,
        unread_only=unread_only,
        limit=limit,
        session=session,
    )
    return [
        EmailItemResponse(
            id=str(item.id),
            sender=item.sender,
            sender_name=item.sender_name,
            recipient=item.recipient,
            subject=item.subject,
            body=item.body,
            thread_id=item.thread_id,
            account_id=str(item.account_id) if item.account_id else None,
            account_label=item.account_label,
            is_read=item.is_read,
            received_at=item.received_at.isoformat(),
        )
        for item in items
    ]


@router.get("/emails/{email_id}/thread", response_model=list[EmailItemResponse])
async def get_email_thread(
    email_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> list[EmailItemResponse]:
    """Retrieve full email conversation context and thread history."""
    thread = await CommunicationService.get_email_thread(
        user_id=str(current_user.id),
        email_id=email_id,
        session=session,
    )
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email thread not found",
        )
    return [
        EmailItemResponse(
            id=str(item.id),
            sender=item.sender,
            sender_name=item.sender_name,
            recipient=item.recipient,
            subject=item.subject,
            body=item.body,
            thread_id=item.thread_id,
            account_id=str(item.account_id) if item.account_id else None,
            account_label=item.account_label,
            is_read=item.is_read,
            received_at=item.received_at.isoformat(),
        )
        for item in thread
    ]


@router.post("/emails/{email_id}/draft-reply", response_model=DraftReplyResponse)
async def draft_email_reply(
    email_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
    request: DraftReplyRequest | None = None,
) -> DraftReplyResponse:
    """Generate a completely human, context-aware email reply from thread history."""
    thread = await CommunicationService.get_email_thread(
        user_id=str(current_user.id),
        email_id=email_id,
        session=session,
    )
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found",
        )

    target_email = thread[-1]
    instructions = request.user_instructions if request else None

    draft_text = CommunicationService.draft_human_email_reply(
        target_email=target_email,
        thread=thread,
        user_instructions=instructions,
        user_display_name=current_user.name or current_user.username or "Vishal",
    )

    return DraftReplyResponse(
        draft_reply=draft_text,
        recipient=target_email.sender,
        channel="email",
        context_summary=f"Reply to {target_email.sender_name} regarding '{target_email.subject}'",
    )


@router.get("/whatsapp", response_model=list[WhatsAppItemResponse])
async def list_whatsapp_messages(
    current_user: CurrentUser,
    session: DbSession,
    sender: Annotated[str | None, Query(description="Filter by contact name")] = None,
    account_label: Annotated[
        str | None,
        Query(description="Filter by account label (e.g. WhatsApp Personal, WhatsApp Business)"),
    ] = None,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[WhatsAppItemResponse]:
    """Check received WhatsApp messages from a particular contact, account, or all contacts."""
    items = await CommunicationService.get_whatsapp_messages(
        user_id=str(current_user.id),
        sender_name=sender,
        account_label_query=account_label,
        unread_only=unread_only,
        limit=limit,
        session=session,
    )
    return [
        WhatsAppItemResponse(
            id=str(item.id),
            sender=item.sender,
            sender_name=item.sender_name,
            recipient=item.recipient,
            body=item.body,
            account_id=str(item.account_id) if item.account_id else None,
            account_label=item.account_label,
            is_read=item.is_read,
            received_at=item.received_at.isoformat(),
        )
        for item in items
    ]


@router.post("/whatsapp/draft-reply", response_model=DraftReplyResponse)
async def draft_whatsapp_reply(
    current_user: CurrentUser,
    session: DbSession,
    sender: Annotated[str, Query(description="Contact name to reply to")],
    request: DraftReplyRequest | None = None,
) -> DraftReplyResponse:
    """Generate a warm, natural, human WhatsApp reply based on recent chat context."""
    recent_msgs = await CommunicationService.get_whatsapp_messages(
        user_id=str(current_user.id),
        sender_name=sender,
        limit=10,
        session=session,
    )
    if not recent_msgs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No recent messages found from '{sender}'",
        )

    instructions = request.user_instructions if request else None
    draft_text = CommunicationService.draft_human_whatsapp_reply(
        recent_messages=recent_msgs,
        user_instructions=instructions,
    )

    return DraftReplyResponse(
        draft_reply=draft_text,
        recipient=recent_msgs[0].sender,
        channel="whatsapp",
        context_summary=f"Reply to {recent_msgs[0].sender_name} based on recent messages",
    )


@router.post("/meetings/schedule", status_code=status.HTTP_201_CREATED)
async def schedule_meeting(
    request: ScheduleMeetingRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    """Schedule meeting on specific day and time, and invite participants."""
    proposal = await CommunicationService.schedule_meeting_action(
        user_id=str(current_user.id),
        title=request.title,
        date=request.date,
        start_time=request.time,
        attendees=request.attendees,
        description=request.description,
        session=session,
    )

    if request.auto_confirm:
        from app.services.action_service import ActionService

        confirmed_prop = await ActionService.confirm_action(
            user_id=str(current_user.id),
            proposal_id=str(proposal.id),
            confirmed=True,
            session=session,
        )
        params = confirmed_prop.parameters or {}
        meet_link = params.get("meet_link")
        cal_created = params.get("calendar_created", False)
        reauth_needed = params.get("requires_calendar_reauth", False)

        attendees_str = ", ".join(request.attendees)
        msg = (
            f"Meeting scheduled! Google Meet link: {meet_link}. "
            f"Calendar invite emails sent to {attendees_str}."
        )
        if cal_created:
            msg += " Direct Google Calendar event created."
        elif reauth_needed:
            msg += (
                " (Note: Direct Google Calendar sync requires calendar scope re-authorization; "
                "calendar invite email with RSVP was sent via Gmail)."
            )

        return {
            "proposal_id": str(confirmed_prop.id),
            "status": confirmed_prop.status,
            "description": confirmed_prop.description,
            "meet_link": meet_link,
            "calendar_created": cal_created,
            "requires_calendar_reauth": reauth_needed,
            "message": msg,
        }

    meet_link = (proposal.parameters or {}).get("meet_link")
    return {
        "proposal_id": str(proposal.id),
        "status": proposal.status,
        "description": proposal.description,
        "meet_link": meet_link,
        "action_required": (
            f"Action proposal created and awaiting confirmation. "
            f'Call POST /actions/{proposal.id}/confirm with {{"confirmed": true}} '
            "to dispatch invitation emails, or pass auto_confirm=true."
        ),
    }


@router.post("/seed", status_code=status.HTTP_201_CREATED)
async def seed_incoming_communication(
    request: SeedCommunicationRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> dict[str, str]:
    """Seed incoming email or WhatsApp message for testing and synchronization."""
    target_account_uuid = UUID(str(request.account_id)) if request.account_id else None
    item = CommunicationItem(
        user_id=str(current_user.id),
        channel=request.channel,
        sender=request.sender,
        sender_name=request.sender_name,
        recipient=request.recipient,
        subject=request.subject,
        body=request.body,
        thread_id=request.thread_id,
        account_id=target_account_uuid,
        account_label=request.account_label,
        is_read=False,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return {"id": str(item.id), "status": "seeded"}


@router.post("/emails/sync-real", status_code=status.HTTP_200_OK)
async def sync_real_emails(
    request: SyncRealEmailRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    """Sync real emails from real inbox over IMAP SSL."""
    synced = await CommunicationService.sync_real_emails_via_imap(
        user_id=str(current_user.id),
        session=session,
        imap_host=request.imap_host,
        imap_port=request.imap_port,
        email_user=request.email_user,
        email_password=request.email_password,
        limit=request.limit,
    )
    return {
        "status": "success",
        "synced_count": len(synced),
        "message": f"Successfully synced {len(synced)} real emails from inbox.",
    }


@router.post("/emails/send-real", status_code=status.HTTP_200_OK)
async def send_real_email(
    request: SendRealEmailRequest,
    current_user: CurrentUser,
) -> dict[str, str]:
    """Send real outgoing email over SMTP SSL."""
    sent = CommunicationService.send_real_email_via_smtp(
        recipient=request.recipient,
        subject=request.subject,
        body=request.body,
        smtp_host=request.smtp_host,
        smtp_port=request.smtp_port,
        email_user=request.email_user,
        email_password=request.email_password,
    )
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to send real email. Check SMTP settings and credentials.",
        )
    return {
        "status": "sent",
        "recipient": request.recipient,
        "subject": request.subject,
    }
