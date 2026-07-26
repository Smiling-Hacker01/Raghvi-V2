"""Task model — user goals and todo items."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Index, String, Text, Uuid

from app.db.base import Base


class TaskStatus(StrEnum):
    """Task lifecycle states."""

    PENDING = "pending"  # Not started
    IN_PROGRESS = "in_progress"  # Started
    COMPLETED = "completed"  # Done
    ARCHIVED = "archived"  # Inactive


class TaskPriority(StrEnum):
    """Task priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Task(Base):
    """User task/goal.

    Represents a goal or task the user wants to accomplish.
    Can be created manually or extracted from chat.
    Integrated with memory system for context.
    """

    __tablename__ = "tasks"

    id = Column(Uuid, primary_key=True, default=uuid4)
    user_id = Column(String(36), nullable=False, index=True)

    # Task content
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)

    # Status & priority
    status = Column(String(20), default=TaskStatus.PENDING, nullable=False)
    priority = Column(String(20), default=TaskPriority.MEDIUM, nullable=False)

    # Dates
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
    )
    due_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Metadata
    tags = Column(String(500), nullable=True)  # Comma-separated
    auto_extracted = Column(Boolean, default=False, nullable=False)  # From chat extraction

    # Soft delete
    deleted_at = Column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_task_user_status", "user_id", "status"),
        Index("ix_task_user_priority", "user_id", "priority"),
        Index("ix_task_due_date", "user_id", "due_date"),
    )

    def __repr__(self) -> str:
        return f"<Task id={self.id} title={self.title} status={self.status}>"

    @property
    def is_active(self) -> bool:
        """Task is not deleted."""
        return self.deleted_at is None

    @property
    def is_completed(self) -> bool:
        """Task is done."""
        return self.status == TaskStatus.COMPLETED
