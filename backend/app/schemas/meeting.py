"""Pydantic schemas for meeting notes and transcription summaries."""

from typing import Any

from pydantic import BaseModel, Field


class MeetingCreateRequest(BaseModel):
    """Payload to create or process a meeting transcript."""

    title: str = Field(..., min_length=1, max_length=200, description="Meeting title or subject")
    transcript: str = Field(..., min_length=1, description="Raw transcript or conversation text")
    duration_seconds: int = Field(default=0, ge=0, description="Duration of meeting in seconds")
    meeting_date: str | None = Field(default=None, description="ISO-formatted meeting datetime")


class MeetingUpdateRequest(BaseModel):
    """Payload to edit extracted meeting notes."""

    title: str | None = None
    summary: str | None = None
    key_decisions: list[str] | None = None
    discussion_points: list[str] | None = None
    action_items: list[dict[str, Any]] | None = None


class MeetingNoteResponse(BaseModel):
    """Response representation of a meeting note."""

    id: str
    title: str
    meeting_date: str
    duration_seconds: int
    raw_transcript: str
    summary: str
    key_decisions: list[str]
    discussion_points: list[str]
    action_items: list[dict[str, Any]]
    confidence_score: float
    uncertainty_notes: str | None = None
    created_at: str
    updated_at: str


class MeetingListResponse(BaseModel):
    """List of meeting notes."""

    meetings: list[MeetingNoteResponse]
    total: int
