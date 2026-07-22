"""Memory model — user facts that Raghvi learns and remembers."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Index, String, Text, Uuid

from app.db.base import Base


class Memory(Base):
    """User memory/fact that Raghvi remembers.

    Represents information the user has shared that Raghvi should remember.

    Attributes:
        id: Unique memory identifier (UUID)
        user_id: User who owns this memory (foreign key)
        content: The actual memory text
        is_sensitive: True if contains PII (email, phone, address)
        is_encrypted: True if content is encrypted in database
        approved_at: When user approved (NULL = pending, datetime = approved)
        created_at: Creation timestamp
        updated_at: Last update timestamp
        deleted_at: Soft delete timestamp (NULL = active, datetime = deleted)

    Approval Logic:
        - Non-sensitive (public data): Auto-approved at creation
        - Sensitive (email, phone, address): Pending user approval
        - Critical (password, card, SSN): Never auto-approved, flagged for review
    """

    __tablename__ = "memories"

    id = Column(Uuid, primary_key=True, default=uuid4)
    user_id = Column(String(36), nullable=False, index=True)
    content = Column(Text, nullable=False)
    is_sensitive = Column(Boolean, default=False, nullable=False)
    is_encrypted = Column(Boolean, default=False, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    # Composite indexes for common queries
    __table_args__ = (
        Index("ix_memory_user_approved", "user_id", "approved_at"),
        Index("ix_memory_user_sensitive", "user_id", "is_sensitive"),
        Index("ix_memory_created_desc", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Memory id={self.id} user_id={self.user_id} "
            f"sensitive={self.is_sensitive} approved={self.is_approved}>"
        )

    @property
    def is_approved(self) -> bool:
        """Check if memory is approved."""
        return self.approved_at is not None

    @property
    def is_active(self) -> bool:
        """Check if memory is not soft-deleted."""
        return self.deleted_at is None

    @property
    def is_pending(self) -> bool:
        """Check if memory is pending approval."""
        return self.approved_at is None and self.deleted_at is None
