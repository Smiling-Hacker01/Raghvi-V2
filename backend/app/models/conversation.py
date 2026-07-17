from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, Uuid
from sqlalchemy.orm import relationship

from app.db.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Uuid, primary_key=True, default=uuid4)
    user_id = Column(Uuid, nullable=False, index=True)  # FK to users(id), added via Alembic
    title = Column(String(255), default="Conversation")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to messages (lazy load)
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} user_id={self.user_id}>"