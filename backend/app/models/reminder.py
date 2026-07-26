"""Reminder model — task reminders and notifications."""

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Index, String, Uuid

from app.db.base import Base


class ReminderType(StrEnum):
    """Reminder types."""

    DUE_SOON = "due_soon"  # Task due in 1 day
    OVERDUE = "overdue"  # Task is overdue
    CUSTOM = "custom"  # Custom reminder time


class Reminder(Base):
    """Task reminder."""

    __tablename__ = "reminders"

    id = Column(Uuid, primary_key=True, default=uuid4)
    task_id = Column(Uuid, nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)

    reminder_type = Column(String(20), default=ReminderType.DUE_SOON)
    reminder_time = Column(DateTime, nullable=False)  # When to remind

    sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_reminder_user_sent", "user_id", "sent"),
        Index("ix_reminder_time", "reminder_time"),
    )

    def __repr__(self) -> str:
        return f"<Reminder task_id={self.task_id} type={self.reminder_type}>"
