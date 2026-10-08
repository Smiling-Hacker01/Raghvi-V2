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
    provider_name: str | None = None
    provider_subscription_id: str | None = None


class CreateSubscriptionRequest(BaseModel):
    """Request to upgrade subscription."""

    plan_id: str = Field(..., description="Plan ID: 'pro', 'premium', 'platinum'")


class UpgradeSubscriptionRequest(BaseModel):
    """Request to change subscription plan."""

    new_plan_id: str = Field(..., description="New plan ID")
    proration: bool = Field(True, description="Apply proration for mid-cycle changes")


class CancelSubscriptionRequest(BaseModel):
    """Request to cancel subscription."""

    reason: str | None = Field(None, description="Cancellation reason")
    feedback: str | None = Field(None, description="User feedback")


class CheckoutSessionRequest(BaseModel):
    """Request to create a checkout session."""

    plan_id: str = Field(..., description="Plan ID: 'pro', 'premium', 'platinum'")
    success_url: str = Field(..., description="URL to redirect after successful payment")
    cancel_url: str = Field(..., description="URL to redirect if payment is cancelled")
    metadata: dict[str, str] | None = Field(None, description="Additional metadata")


class CheckoutSessionResponse(BaseModel):
    """Provider-neutral checkout session response."""

    provider_name: str
    session_id: str
    checkout_url: str
    expires_at: int | None = None


class SubscriptionListResponse(BaseModel):
    """List of available plans."""

    plans: list[SubscriptionPlanResponse]
    user_current_plan: str | None  # Current plan ID if subscribed
