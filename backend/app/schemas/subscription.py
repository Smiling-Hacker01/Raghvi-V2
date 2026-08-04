"""Pydantic schemas for subscription operations."""

from pydantic import BaseModel, Field


class SubscriptionPlanResponse(BaseModel):
    """Subscription plan details."""

    id: str
    name: str
    description: str | None
    price_usd: float
    billing_cycle: str
    max_custom_voices: int
    supported_languages: str
    daily_message_limit: int | None
    priority_support: bool
    family_sharing_slots: int


class UserSubscriptionResponse(BaseModel):
    """User's subscription info."""

    id: str
    user_id: str
    plan_id: str
    plan_name: str  # From joined plan
    started_at: str
    expires_at: str
    is_active: bool
    is_expired: bool
    days_remaining: int
    auto_renew: bool
    stripe_subscription_id: str | None


class CreateSubscriptionRequest(BaseModel):
    """Request to upgrade subscription."""

    plan_id: str = Field(..., description="Plan ID: 'pro', 'premium', 'platinum'")
    stripe_payment_token: str | None = Field(None, description="Stripe token for payment")


class UpgradeSubscriptionRequest(BaseModel):
    """Request to change subscription plan."""

    new_plan_id: str = Field(..., description="New plan ID")
    proration: bool = Field(True, description="Apply proration for mid-cycle changes")


class CancelSubscriptionRequest(BaseModel):
    """Request to cancel subscription."""

    reason: str | None = Field(None, description="Cancellation reason")
    feedback: str | None = Field(None, description="User feedback")


class SubscriptionListResponse(BaseModel):
    """List of available plans."""

    plans: list[SubscriptionPlanResponse]
    user_current_plan: str | None  # Current plan ID if subscribed
