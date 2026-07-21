from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    conversation_id = Column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    tokens_used = Column(Integer, nullable=True)  # Track LLM token usage
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationship to conversation
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message id={self.id} role={self.role} tokens={self.tokens_used}>"
