"""Meeting notes and transcript processing endpoints."""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.meeting import (
    MeetingCreateRequest,
    MeetingListResponse,
    MeetingNoteResponse,
    MeetingUpdateRequest,
)
from app.services.meeting_service import MeetingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["meetings"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def _to_response(note) -> MeetingNoteResponse:
    return MeetingNoteResponse(
        id=str(note.id),
        title=note.title,
        meeting_date=note.meeting_date.isoformat(),
        duration_seconds=note.duration_seconds,
        raw_transcript=note.raw_transcript,
        summary=note.summary,
        key_decisions=note.key_decisions,
        discussion_points=note.discussion_points,
        action_items=note.action_items,
        confidence_score=note.confidence_score,
        uncertainty_notes=note.uncertainty_notes,
        created_at=note.created_at.isoformat(),
        updated_at=note.updated_at.isoformat(),
    )


@router.post("", response_model=MeetingNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting_note(
    request: MeetingCreateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> MeetingNoteResponse:
    """Create meeting note and extract executive summary, decisions, and action items."""
    meeting_dt = None
    if request.meeting_date:
        try:
            meeting_dt = datetime.fromisoformat(request.meeting_date)
        except ValueError:
            meeting_dt = None

    note = await MeetingService.create_meeting_note(
        user_id=str(current_user.id),
        title=request.title,
        transcript=request.transcript,
        duration_seconds=request.duration_seconds,
        meeting_date=meeting_dt,
        session=session,
    )
    return _to_response(note)


@router.post(
    "/upload-audio",
    response_model=MeetingNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_meeting_audio(
    current_user: CurrentUser,
    session: DbSession,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form()] = "Meeting Recording",
) -> MeetingNoteResponse:
    """Listen to meeting audio recording, auto-transcribe, and extract decisions."""
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file cannot be empty",
        )

    transcript = await MeetingService.transcribe_meeting_audio(
        content, filename=file.filename or "meeting.m4a"
    )
    note = await MeetingService.create_meeting_note(
        user_id=str(current_user.id),
        title=title,
        transcript=transcript,
        duration_seconds=0,
        session=session,
    )
    return _to_response(note)


@router.get("", response_model=MeetingListResponse)
async def list_meeting_notes(
    current_user: CurrentUser,
    session: DbSession,
    q: Annotated[str | None, Query(description="Search title or summary")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MeetingListResponse:
    """List and search meeting notes for current user."""
    notes = await MeetingService.get_meeting_notes(
        user_id=str(current_user.id),
        search_query=q,
        limit=limit,
        session=session,
    )
    return MeetingListResponse(
        meetings=[_to_response(n) for n in notes],
        total=len(notes),
    )


@router.get("/{meeting_id}", response_model=MeetingNoteResponse)
async def get_meeting_note(
    meeting_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> MeetingNoteResponse:
    """Retrieve details of a specific meeting note."""
    note = await MeetingService.get_meeting_note(str(current_user.id), meeting_id, session)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting note not found",
        )
    return _to_response(note)


@router.patch("/{meeting_id}", response_model=MeetingNoteResponse)
async def update_meeting_note(
    meeting_id: UUID,
    request: MeetingUpdateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> MeetingNoteResponse:
    """Apply corrections or edits to a meeting note."""
    updates = request.model_dump(exclude_unset=True)
    note = await MeetingService.update_meeting_note(
        user_id=str(current_user.id),
        note_id=meeting_id,
        updates=updates,
        session=session,
    )
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting note not found",
        )
    return _to_response(note)


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting_note(
    meeting_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> None:
    """Soft-delete a meeting note."""
    deleted = await MeetingService.delete_meeting_note(
        user_id=str(current_user.id),
        note_id=meeting_id,
        session=session,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting note not found",
        )


@router.get("/{meeting_id}/export")
async def export_meeting_note_markdown(
    meeting_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> Response:
    """Export meeting notes as formatted markdown text."""
    note = await MeetingService.get_meeting_note(str(current_user.id), meeting_id, session)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting note not found",
        )
    md_content = MeetingService.export_as_markdown(note)
    return Response(content=md_content, media_type="text/markdown")
