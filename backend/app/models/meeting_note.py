"""Meeting note model — stores transcripts, summaries, decisions, and action items."""

from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, Float, Index, Integer, String, Text, Uuid

from app.db.base import Base, get_utc_now


class MeetingNote(Base):
    """User meeting notes with extracted action items, decisions, and transcripts."""

    __tablename__ = "meeting_notes"

    id = Column(Uuid, primary_key=True, default=uuid4)
    user_id = Column(String(36), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    meeting_date = Column(DateTime, default=get_utc_now, nullable=False)
    duration_seconds = Column(Integer, default=0, nullable=False)

    raw_transcript = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    key_decisions = Column(JSON, default=list, nullable=False)
    discussion_points = Column(JSON, default=list, nullable=False)
    action_items = Column(JSON, default=list, nullable=False)

    confidence_score = Column(Float, default=1.0, nullable=False)
    uncertainty_notes = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=get_utc_now, nullable=False)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_meeting_notes_user_date", "user_id", "meeting_date"),
        Index("ix_meeting_notes_user_deleted", "user_id", "deleted_at"),
    )
