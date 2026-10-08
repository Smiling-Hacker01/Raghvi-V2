"""Base payment provider interface."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass
class PaymentProviderConfig:
    """Configuration for a payment provider."""

    name: str
    api_key: str | None = None
    publishable_key: str | None = None
    webhook_secret: str | None = None
    extra: dict[str, Any] | None = None


@dataclass
class CheckoutSessionRequest:
    """Request to create a checkout session."""

    user_id: str
    plan_id: str
    success_url: str
    cancel_url: str
    customer_email: str | None = None
    metadata: dict[str, str] | None = None
    amount_cents: int | None = None
    currency: str = "usd"
    billing_cycle: str = "month"
    plan_name: str | None = None


@dataclass
class CheckoutSessionResponse:
    """Response from creating a checkout session."""

    session_id: str
    url: str
    expires_at: int | None = None


@dataclass
class SubscriptionData:
    """Subscription data from provider."""

    provider_subscription_id: str
    provider_customer_id: str
    status: str  # active, canceled, past_due, trialing, etc.
    current_period_end: int | None = None  # Unix timestamp
    plan_id: str | None = None


@dataclass
class CustomerData:
    """Customer data from provider."""

    provider_customer_id: str
    email: str | None = None
    metadata: dict[str, str] | None = None


@dataclass
class PaymentWebhookEvent:
    """Provider-neutral representation of a verified webhook event."""

    event_type: str
    data: dict[str, Any]
    event_id: str | None = None


class PaymentProviderError(Exception):
    """Base exception for payment provider errors."""

    def __init__(self, message: str, provider: str, code: str | None = None):
        super().__init__(message)
        self.provider = provider
        self.code = code


class PaymentProvider(ABC):
    """Abstract base class for payment providers."""

    def __init__(self, config: PaymentProviderConfig):
        """Initialize provider with configuration."""
        self.config = config

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get provider name."""
        pass

    @abstractmethod
    async def create_checkout_session(
        self, request: CheckoutSessionRequest
    ) -> CheckoutSessionResponse:
        """Create a checkout session for subscription upgrade."""
        pass

    @abstractmethod
    async def create_customer(
        self, user_id: str, email: str, metadata: dict[str, str] | None = None
    ) -> CustomerData:
        """Create a customer in the payment provider."""
        pass

    @abstractmethod
    async def get_customer(self, customer_id: str) -> CustomerData:
        """Retrieve customer from provider."""
        pass

    @abstractmethod
    async def get_subscription(self, subscription_id: str) -> SubscriptionData:
        """Retrieve subscription from provider."""
        pass

    @abstractmethod
    async def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel a subscription at the provider."""
        pass

    @abstractmethod
    async def verify_webhook_signature(
        self, payload: bytes, headers: Mapping[str, str]
    ) -> PaymentWebhookEvent:
        """Verify a webhook and normalize its event for the application."""
        pass
