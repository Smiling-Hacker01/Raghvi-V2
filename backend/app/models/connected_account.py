"""Connected account model — stores encrypted email & messaging credentials per user."""

from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text, Uuid

from app.db.base import Base, get_utc_now


class ConnectedAccount(Base):
    """User connected email or messaging account (e.g. Gmail, Outlook, WhatsApp)."""

    __tablename__ = "connected_accounts"

    id = Column(Uuid, primary_key=True, default=uuid4)
    user_id = Column(String(36), nullable=False, index=True)
    account_type = Column(String(20), nullable=False)  # "email", "whatsapp"
    # Providers: gmail, outlook, yahoo, icloud, custom_imap, whatsapp_companion
    provider = Column(String(50), nullable=False)
    account_label = Column(String(100), nullable=False)  # e.g., "Personal Gmail", "Work Outlook"
    identifier = Column(String(150), nullable=False)  # email address or phone number
    encrypted_credentials = Column(
        Text, nullable=True
    )  # AES-256-GCM encrypted serialized credentials
    is_primary = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    sync_interval_minutes = Column(Integer, default=15, nullable=False)
    last_synced_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=get_utc_now, nullable=False)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False)

    __table_args__ = (
        Index("ix_conn_user_type", "user_id", "account_type"),
        Index("ix_conn_user_active", "user_id", "is_active"),
        Index("ix_conn_user_label", "user_id", "account_label"),
    )
