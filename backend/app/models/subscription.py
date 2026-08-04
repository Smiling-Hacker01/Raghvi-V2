"""Subscription models — plans and user subscriptions."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, Uuid

from app.db.base import Base, get_utc_now


class SubscriptionPlan(Base):
    """Subscription plan tier (FREE, PRO, PREMIUM, PLATINUM)."""

    __tablename__ = "subscription_plans"

    id = Column(String(50), primary_key=True)  # "free", "pro", "premium", "platinum"
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)

    # Pricing
    price_usd = Column(Float, nullable=False, default=0.0)
    billing_cycle = Column(String(20), nullable=False, default="monthly")  # "monthly", "yearly"

    # Voice features
    max_custom_voices = Column(Integer, nullable=False, default=0)
    supported_languages = Column(String(500), nullable=False, default="en")  # "en,hi"
    system_voices_available = Column(Boolean, nullable=False, default=True)

    # Chat features
    daily_message_limit = Column(Integer, nullable=True)  # None = unlimited

    # Other features
    priority_support = Column(Boolean, nullable=False, default=False)
    family_sharing_slots = Column(Integer, nullable=False, default=0)

    # Metadata
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=get_utc_now)
    updated_at = Column(DateTime, nullable=False, default=get_utc_now, onupdate=get_utc_now)

    def __repr__(self) -> str:
        return f"<SubscriptionPlan id={self.id} name={self.name} price=${self.price_usd}>"


class UserSubscription(Base):
    """User's active subscription."""

    __tablename__ = "user_subscriptions"

    id = Column(Uuid, primary_key=True, default=uuid4)
    user_id = Column(String(36), nullable=False, unique=True, index=True)

    # Plan reference
    plan_id = Column(String(50), nullable=False)  # FK to SubscriptionPlan.id

    # Subscription lifecycle
    started_at = Column(DateTime, nullable=False, default=get_utc_now)
    expires_at = Column(DateTime, nullable=False)  # When subscription expires
    renewed_at = Column(DateTime, nullable=True)  # Last renewal date

    # Status
    is_active = Column(Boolean, nullable=False, default=True)

    # Billing
    stripe_subscription_id = Column(String(100), nullable=True)  # Stripe subscription ID
    stripe_customer_id = Column(String(100), nullable=True)  # Stripe customer ID
    auto_renew = Column(Boolean, nullable=False, default=True)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=get_utc_now)
    updated_at = Column(DateTime, nullable=False, default=get_utc_now, onupdate=get_utc_now)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete


    __table_args__ = (
        Index("ix_user_sub_active", "user_id", "is_active"),
        Index("ix_user_sub_expires", "user_id", "expires_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserSubscription user_id={self.user_id} "
            f"plan={self.plan_id} expires={self.expires_at}>"
        )

    @property
    def is_expired(self) -> bool:
        """Check if subscription is expired."""
        if not self.expires_at:
            return True
        # Make both timezone-aware for comparison
        now_utc = datetime.now(UTC)
        expires_at_utc = (
            self.expires_at.replace(tzinfo=UTC)
            if self.expires_at.tzinfo is None
            else self.expires_at
        )
        return now_utc > expires_at_utc

    @property
    def days_remaining(self) -> int:
        """Days until expiration."""
        if self.is_expired:
            return 0
        # Make both timezone-aware for comparison
        now_utc = datetime.now(UTC)
        expires_at_utc = (
            self.expires_at.replace(tzinfo=UTC)
            if self.expires_at.tzinfo is None
            else self.expires_at
        )
        delta = expires_at_utc - now_utc
        return delta.days
