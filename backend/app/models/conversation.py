from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import relationship

from app.db.base import Base


def get_utc_now():
    # Return naive UTC datetime to satisfy asyncpg's TIMESTAMP WITHOUT TIME ZONE
    # while avoiding the Python 3.12+ datetime.utcnow() deprecation warning
    return datetime.now(UTC).replace(tzinfo=None)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    # NOTE: User.id is String(36) (JWT layer extracts user_id as a plain string).
    # Conversation.user_id must match that type for SQLAlchemy bind-processor
    # compatibility (Uuid type calls .hex on values; str objects don't have .hex).
    # TODO: Unify to native Uuid(as_uuid=True) across all models in a future sprint.
    user_id = Column(String(36), nullable=False, unique=True, index=True)
    title = Column(String(255), default="Conversation")
    created_at = Column(DateTime, nullable=False, default=get_utc_now)
    updated_at = Column(DateTime, nullable=False, default=get_utc_now, onupdate=get_utc_now)

    # Relationship to messages (lazy load)
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} user_id={self.user_id}>"
