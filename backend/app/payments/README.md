# Payment provider adapters

`PaymentProvider` is the integration boundary. An adapter handles provider API
operations and signature verification, then translates webhook payloads into
`PaymentWebhookEvent` names and fields. `PaymentWebhookService` owns subscription
and renewal updates, so adapters do not need to write application database logic.

To add a provider:

1. Implement `PaymentProvider` in `app/payments/providers/`.
2. Normalize webhook events to `subscription.created`, `subscription.updated`,
   `subscription.deleted`, `payment.succeeded`, `payment.failed`, or
   `checkout.completed`.
3. Register it during application startup with
   `PaymentAdapterBuilder.register_provider("provider_name", ProviderClass)`.
4. Configure `PAYMENT_PROVIDER=provider_name` and provider credentials in
   `PAYMENT_PROVIDER_CONFIG` as a JSON object. The adapter receives shared
   `api_key`, `publishable_key`, and `webhook_secret` fields plus provider-specific
   values in `PaymentProviderConfig.extra`.
5. Point the provider webhook to `/webhooks/provider_name`.

Subscription records store the provider name and provider identifiers. The
`d6a7f90b1c42` migration copies existing Stripe IDs into those fields while
retaining the legacy Stripe columns for compatibility.
