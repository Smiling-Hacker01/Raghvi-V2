"""Communication item model — stores emails and messaging chats (WhatsApp/SMS)."""

from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Index, String, Text, Uuid

from app.db.base import Base, get_utc_now


class CommunicationItem(Base):
    """User email or messaging conversation message."""

    __tablename__ = "communication_items"

    id = Column(Uuid, primary_key=True, default=uuid4)
    user_id = Column(String(36), nullable=False, index=True)
    channel = Column(String(20), nullable=False)  # "email", "whatsapp", "sms"
    sender = Column(String(150), nullable=False)
    sender_name = Column(String(100), nullable=False)
    recipient = Column(String(150), nullable=False)
    subject = Column(String(255), nullable=True)
    body = Column(Text, nullable=False)
    thread_id = Column(String(100), nullable=True, index=True)
    account_id = Column(Uuid, nullable=True, index=True)
    account_label = Column(String(100), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)

    received_at = Column(DateTime, default=get_utc_now, nullable=False)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)

    __table_args__ = (
        Index("ix_comm_user_channel_read", "user_id", "channel", "is_read"),
        Index("ix_comm_user_sender", "user_id", "sender_name"),
        Index("ix_comm_user_account", "user_id", "account_id"),
    )
