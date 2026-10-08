"""Register and construct the configured payment provider adapter."""

from collections.abc import Callable

from app.core.config import get_settings
from app.payments.base import PaymentProvider, PaymentProviderConfig
from app.payments.providers.stripe_provider import StripeProvider

ProviderFactory = Callable[[PaymentProviderConfig], PaymentProvider]


class PaymentAdapterBuilder:
    """Registry-backed builder for payment provider plugins."""

    _factories: dict[str, ProviderFactory] = {"stripe": StripeProvider}

    @classmethod
    def register_provider(cls, name: str, factory: ProviderFactory) -> None:
        """Register a provider factory under its stable configuration name."""
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("Payment provider name cannot be empty")
        if normalized in cls._factories:
            raise ValueError(f"Payment provider '{normalized}' is already registered")
        cls._factories[normalized] = factory

    @classmethod
    def build_provider(cls, provider_name: str | None = None) -> PaymentProvider:
        """Build the configured provider or a named registered plugin."""
        settings = get_settings()
        name = (provider_name or settings.payment_provider).strip().lower()
        factory = cls._factories.get(name)
        if factory is None:
            available = ", ".join(sorted(cls._factories))
            raise ValueError(f"Unknown payment provider '{name}'. Registered: {available}")

        if name == "stripe":
            config = PaymentProviderConfig(
                name=name,
                api_key=settings.stripe_api_key,
                publishable_key=settings.stripe_publishable_key,
                webhook_secret=settings.stripe_webhook_secret,
                extra={
                    **settings.payment_provider_config,
                    "default_plan_id": "pro",
                },
            )
        else:
            extra = dict(settings.payment_provider_config)
            config = PaymentProviderConfig(
                name=name,
                api_key=extra.pop("api_key", None),
                publishable_key=extra.pop("publishable_key", None),
                webhook_secret=extra.pop("webhook_secret", None),
                extra=extra,
            )

        return factory(config)


_payment_providers: dict[str, PaymentProvider] = {}


def get_payment_provider(provider_name: str | None = None) -> PaymentProvider:
    """Get a cached adapter instance for the configured or named provider."""
    name = (provider_name or get_settings().payment_provider).strip().lower()
    if name not in _payment_providers:
        _payment_providers[name] = PaymentAdapterBuilder.build_provider(name)
    return _payment_providers[name]


def reset_payment_provider() -> None:
    """Clear cached adapters, primarily for tests and runtime reconfiguration."""
    _payment_providers.clear()
