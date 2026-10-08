"""Stripe implementation of the provider-neutral payment contract."""

import logging
from collections.abc import Mapping
from typing import Any

import stripe

from app.payments.base import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    CustomerData,
    PaymentProvider,
    PaymentProviderConfig,
    PaymentProviderError,
    PaymentWebhookEvent,
    SubscriptionData,
)

logger = logging.getLogger(__name__)


class StripeProvider(PaymentProvider):
    """Stripe adapter; Stripe event names and payloads stay inside this class."""

    def __init__(self, config: PaymentProviderConfig):
        super().__init__(config)
        # The application selects one active provider; set the key explicitly so
        # a stale STRIPE_API_KEY environment variable cannot be used by accident.
        stripe.api_key = config.api_key or ""
        self.publishable_key = config.publishable_key

    @property
    def provider_name(self) -> str:
        return "stripe"

    async def create_checkout_session(
        self, request: CheckoutSessionRequest
    ) -> CheckoutSessionResponse:
        """Create a subscription checkout using the server-calculated price."""
        if request.amount_cents is None or request.amount_cents < 0:
            raise PaymentProviderError(
                "A valid server-calculated amount is required",
                provider=self.provider_name,
                code="invalid_amount",
            )

        metadata = dict(request.metadata or {})
        metadata.update(
            user_id=request.user_id,
            plan_id=request.plan_id,
            billing_cycle=request.billing_cycle,
        )
        if request.plan_name:
            metadata["plan_name"] = request.plan_name

        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": request.currency,
                            "product_data": {"name": request.plan_name or request.plan_id},
                            "unit_amount": request.amount_cents,
                            "recurring": {"interval": request.billing_cycle},
                        },
                        "quantity": 1,
                    }
                ],
                success_url=request.success_url,
                cancel_url=request.cancel_url,
                customer_email=request.customer_email,
                metadata=metadata,
                subscription_data={"metadata": metadata},
            )
            return CheckoutSessionResponse(
                session_id=session.id,
                url=session.url,
                expires_at=int(session.expires_at) if session.expires_at else None,
            )
        except stripe.error.StripeError as exc:
            raise self._provider_error(exc) from exc

    async def create_customer(
        self, user_id: str, email: str, metadata: dict[str, str] | None = None
    ) -> CustomerData:
        """Create a Stripe customer with the application's user ID attached."""
        customer_metadata = dict(metadata or {})
        customer_metadata["user_id"] = user_id
        try:
            customer = stripe.Customer.create(email=email, metadata=customer_metadata)
            return CustomerData(
                provider_customer_id=customer.id,
                email=customer.email,
                metadata=dict(customer.metadata) if customer.metadata else None,
            )
        except stripe.error.StripeError as exc:
            raise self._provider_error(exc) from exc

    async def get_customer(self, customer_id: str) -> CustomerData:
        """Retrieve a Stripe customer."""
        try:
            customer = stripe.Customer.retrieve(customer_id)
            return CustomerData(
                provider_customer_id=customer.id,
                email=customer.email,
                metadata=dict(customer.metadata) if customer.metadata else None,
            )
        except stripe.error.StripeError as exc:
            raise self._provider_error(exc) from exc

    async def get_subscription(self, subscription_id: str) -> SubscriptionData:
        """Retrieve a Stripe subscription and expose provider-neutral fields."""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return SubscriptionData(
                provider_subscription_id=subscription.id,
                provider_customer_id=self._object_id(subscription.customer),
                status=subscription.status,
                current_period_end=subscription.current_period_end,
                plan_id=subscription.metadata.get("plan_id")
                if subscription.metadata
                else None,
            )
        except stripe.error.StripeError as exc:
            raise self._provider_error(exc) from exc

    async def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel a Stripe subscription."""
        try:
            stripe.Subscription.delete(subscription_id)
            return True
        except stripe.error.StripeError as exc:
            raise self._provider_error(exc) from exc

    async def verify_webhook_signature(
        self, payload: bytes, headers: Mapping[str, str]
    ) -> PaymentWebhookEvent:
        """Verify Stripe's signature and translate its event to app vocabulary."""
        signature = headers.get("stripe-signature") or headers.get("Stripe-Signature")
        if not signature:
            raise PaymentProviderError(
                "Missing Stripe signature header",
                provider=self.provider_name,
                code="missing_signature",
            )

        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                self.config.webhook_secret,
            )
        except stripe.error.SignatureVerificationError as exc:
            raise PaymentProviderError(
                "Invalid webhook signature",
                provider=self.provider_name,
                code="invalid_signature",
            ) from exc
        except ValueError as exc:
            raise PaymentProviderError(
                "Invalid webhook payload",
                provider=self.provider_name,
                code="invalid_payload",
            ) from exc

        raw_object = event["data"]["object"]
        raw_data = raw_object.to_dict() if hasattr(raw_object, "to_dict") else dict(raw_object)
        event_type = event["type"]
        event_id = getattr(event, "id", None)
        normalized_type, normalized_data = await self._normalize_webhook(
            event_type, raw_data
        )
        return PaymentWebhookEvent(
            event_type=normalized_type,
            data=normalized_data,
            event_id=event_id,
        )

    async def _normalize_webhook(
        self, event_type: str, data: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        """Convert Stripe payloads into events the application can process."""
        if event_type in {"customer.subscription.created", "customer.subscription.updated"}:
            customer_id = self._object_id(data.get("customer"))
            metadata = data.get("metadata") or {}
            user_id = metadata.get("user_id")
            if not user_id and customer_id:
                customer = stripe.Customer.retrieve(customer_id)
                user_id = (customer.get("metadata") or {}).get("user_id")
            return (
                "subscription.created"
                if event_type.endswith("created")
                else "subscription.updated",
                {
                    "user_id": user_id,
                    "plan_id": metadata.get("plan_id")
                    or (self.config.extra or {}).get("default_plan_id", "pro"),
                    "provider_subscription_id": data.get("id"),
                    "provider_customer_id": customer_id,
                    "status": data.get("status"),
                    "current_period_end": data.get("current_period_end"),
                },
            )

        if event_type == "customer.subscription.deleted":
            return "subscription.deleted", {
                "provider_subscription_id": data.get("id"),
                "status": data.get("status", "canceled"),
            }

        if event_type == "invoice.payment_succeeded":
            return "payment.succeeded", {
                "provider_subscription_id": self._object_id(data.get("subscription")),
                "provider_payment_id": data.get("id"),
                "billing_reason": data.get("billing_reason"),
                "current_period_end": self._invoice_period_end(data),
            }

        if event_type == "invoice.payment_failed":
            return "payment.failed", {
                "provider_subscription_id": self._object_id(data.get("subscription")),
                "provider_payment_id": data.get("id"),
            }

        if event_type == "checkout.session.completed":
            metadata = data.get("metadata") or {}
            return "checkout.completed", {
                "user_id": metadata.get("user_id"),
                "plan_id": metadata.get("plan_id"),
                "provider_session_id": data.get("id"),
            }

        return event_type, data

    @staticmethod
    def _object_id(value: Any) -> str | None:
        """Return an ID from either a Stripe ID string or expanded object."""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return getattr(value, "id", None)

    @staticmethod
    def _invoice_period_end(data: dict[str, Any]) -> int | None:
        """Get the latest subscription-line period end from a Stripe invoice."""
        line_ends = [
            line.get("period", {}).get("end")
            for line in (data.get("lines") or {}).get("data", [])
            if line.get("period", {}).get("end") is not None
        ]
        return max(line_ends) if line_ends else None

    def _provider_error(self, exc: stripe.error.StripeError) -> PaymentProviderError:
        """Translate a Stripe SDK exception to the provider-neutral error."""
        logger.error("Stripe request failed: %s", exc)
        return PaymentProviderError(
            message=str(exc),
            provider=self.provider_name,
            code=getattr(exc, "code", None),
        )
