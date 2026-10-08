"""Tests for the payment provider adapter boundary."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.payments.adapter_builder import (
    PaymentAdapterBuilder,
    get_payment_provider,
    reset_payment_provider,
)
from app.payments.base import (
    CheckoutSessionRequest,
    PaymentProviderConfig,
    PaymentWebhookEvent,
)
from app.payments.providers.stripe_provider import StripeProvider


def test_builder_registers_and_builds_non_stripe_provider(monkeypatch):
    captured = {}

    def factory(config):
        captured["config"] = config
        return object()

    monkeypatch.delitem(PaymentAdapterBuilder._factories, "example", raising=False)
    PaymentAdapterBuilder.register_provider("example", factory)
    monkeypatch.setattr(
        "app.payments.adapter_builder.get_settings",
        lambda: SimpleNamespace(
            payment_provider="example",
            payment_provider_config={
                "api_key": "example-key",
                "webhook_secret": "example-secret",
                "account_id": "acct-1",
            },
        ),
    )

    assert PaymentAdapterBuilder.build_provider() is not None
    config = captured["config"]
    assert config.name == "example"
    assert config.api_key == "example-key"
    assert config.webhook_secret == "example-secret"
    assert config.extra == {"account_id": "acct-1"}


def test_payment_provider_instances_are_cached_and_reset(monkeypatch):
    provider = object()

    def factory(_):
        return provider

    monkeypatch.setitem(PaymentAdapterBuilder._factories, "example", factory)
    monkeypatch.setattr(
        "app.payments.adapter_builder.get_settings",
        lambda: SimpleNamespace(
            payment_provider="example",
            payment_provider_config={},
        ),
    )

    reset_payment_provider()
    assert get_payment_provider() is provider
    assert get_payment_provider("example") is provider
    reset_payment_provider()
    assert get_payment_provider() is provider


@pytest.mark.asyncio
async def test_stripe_checkout_uses_server_supplied_amount_and_preserves_metadata():
    provider = StripeProvider(PaymentProviderConfig(name="stripe", api_key="test-key"))
    metadata = {"source": "checkout"}
    request = CheckoutSessionRequest(
        user_id="user-1",
        plan_id="pro",
        success_url="https://example.test/success",
        cancel_url="https://example.test/cancel",
        metadata=metadata,
        amount_cents=1299,
        billing_cycle="month",
        plan_name="Pro",
    )
    stripe_session = SimpleNamespace(
        id="cs_test",
        url="https://checkout.test/session",
        expires_at=42,
    )

    with patch(
        "app.payments.providers.stripe_provider.stripe.checkout.Session.create",
        return_value=stripe_session,
    ) as create_session:
        result = await provider.create_checkout_session(request)

    assert result.session_id == "cs_test"
    assert result.url == "https://checkout.test/session"
    params = create_session.call_args.kwargs
    assert params["line_items"][0]["price_data"]["unit_amount"] == 1299
    assert params["metadata"]["user_id"] == "user-1"
    assert params["metadata"]["plan_id"] == "pro"
    assert metadata == {"source": "checkout"}


@pytest.mark.asyncio
async def test_stripe_webhook_verification_returns_normalized_event():
    provider = StripeProvider(PaymentProviderConfig(name="stripe", webhook_secret="whsec_test"))
    raw_event = {
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_test"}},
    }
    with patch(
        "app.payments.providers.stripe_provider.stripe.Webhook.construct_event",
        return_value=raw_event,
    ):
        event = await provider.verify_webhook_signature(b"{}", {"stripe-signature": "signature"})

    assert event == PaymentWebhookEvent(
        event_type="checkout.completed",
        data={"user_id": None, "plan_id": None, "provider_session_id": "cs_test"},
    )
