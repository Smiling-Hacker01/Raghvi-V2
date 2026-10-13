"""Action proposal model for safe device actions."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, String, Uuid

from app.db.base import Base, get_utc_now


class ActionProposal(Base):
    """Proposal for safe user-confirmed device action."""

    __tablename__ = "action_proposals"

    id = Column(Uuid, primary_key=True, default=uuid4)
    user_id = Column(String(36), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)
    parameters = Column(JSON, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="awaiting_confirmation")
    description = Column(String(255), nullable=True)

    expires_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=15),
        nullable=False,
    )
    confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)
