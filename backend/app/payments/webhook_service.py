"""Application-level processing for normalized payment events."""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import UserSubscription
from app.payments.base import PaymentWebhookEvent
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)


class PaymentWebhookService:
    """Apply provider-neutral payment events to subscription state."""

    @staticmethod
    async def handle(
        provider_name: str,
        event: PaymentWebhookEvent,
        session: AsyncSession,
    ) -> dict[str, Any]:
        """Dispatch a normalized event with idempotency."""
        from sqlalchemy.exc import IntegrityError

        from app.models.payment import WebhookEvent

        # 1. Log event and acquire idempotency lock via unique constraint
        if not event.event_id:
            logger.warning("Event missing event_id, skipping idempotency check")
            webhook_event = None
        else:
            webhook_event = WebhookEvent(
                provider_name=provider_name,
                event_id=event.event_id,
                event_type=event.event_type,
                payload=event.data,
                processed=False,
            )
            try:
                session.add(webhook_event)
                await session.commit()
            except IntegrityError:
                await session.rollback()
                logger.info(f"Duplicate webhook event ignored: {event.event_id}")
                return {"status": "success", "message": "already processed"}

        # 2. Dispatch to handler
        handlers = {
            "subscription.created": PaymentWebhookService._subscription_created,
            "subscription.updated": PaymentWebhookService._subscription_updated,
            "subscription.deleted": PaymentWebhookService._subscription_deleted,
            "payment.succeeded": PaymentWebhookService._payment_succeeded,
            "payment.failed": PaymentWebhookService._payment_failed,
            "checkout.completed": PaymentWebhookService._checkout_completed,
        }
        handler = handlers.get(event.event_type)

        try:
            if handler is None:
                logger.info("Unhandled %s payment event: %s", provider_name, event.event_type)
                result = {"status": "unhandled", "event_type": event.event_type}
            else:
                result = await handler(provider_name, event.data, session)

            # 3. Mark processed
            if webhook_event:
                webhook_event.processed = True
                webhook_event.processed_at = datetime.now(UTC).replace(tzinfo=None)
                session.add(webhook_event)
                await session.commit()

            return result
        except Exception as e:
            if webhook_event:
                webhook_event.error_message = str(e)[:500]
                session.add(webhook_event)
                await session.commit()
            raise

    @staticmethod
    async def _subscription_created(
        provider_name: str, data: dict[str, Any], session: AsyncSession
    ) -> dict[str, Any]:
        user_id = data.get("user_id")
        plan_id = data.get("plan_id")
        subscription_id = data.get("provider_subscription_id")
        if not user_id or not plan_id or not subscription_id:
            logger.error("Ignoring incomplete %s subscription-created event", provider_name)
            return {"status": "ignored", "reason": "missing subscription metadata"}
        if data.get("status") not in {"active", "trialing"}:
            return {"status": "ignored", "reason": "subscription is not active"}

        await SubscriptionService.create_subscription(
            user_id=user_id,
            plan_id=plan_id,
            provider_name=provider_name,
            provider_subscription_id=subscription_id,
            provider_customer_id=data.get("provider_customer_id"),
            provider_period_end=PaymentWebhookService._period_end(data.get("current_period_end")),
            session=session,
        )
        return {"status": "success", "user_id": user_id, "plan_id": plan_id}

    @staticmethod
    async def _subscription_updated(
        provider_name: str, data: dict[str, Any], session: AsyncSession
    ) -> dict[str, Any]:
        subscription = await PaymentWebhookService._find_subscription(
            provider_name, data.get("provider_subscription_id"), session
        )
        if subscription is None:
            if data.get("status") in {"active", "trialing"}:
                return await PaymentWebhookService._subscription_created(
                    provider_name, data, session
                )
            return {"status": "not_found"}
        status_value = data.get("status")
        if status_value in {"canceled", "cancelled", "unpaid", "incomplete_expired"}:
            if subscription.is_active:
                await SubscriptionService.cancel_subscription(subscription.user_id, session)
        elif status_value == "past_due":
            logger.warning("Payment is past due for subscription %s", subscription.id)
        elif status_value in {"active", "trialing"} and data.get("current_period_end"):
            subscription.expires_at = PaymentWebhookService._period_end(data["current_period_end"])
            await session.commit()
        return {"status": "success"}

    @staticmethod
    async def _subscription_deleted(
        provider_name: str, data: dict[str, Any], session: AsyncSession
    ) -> dict[str, Any]:
        subscription = await PaymentWebhookService._find_subscription(
            provider_name, data.get("provider_subscription_id"), session
        )
        if subscription is None:
            return {"status": "not_found"}
        if subscription.is_active:
            await SubscriptionService.cancel_subscription(subscription.user_id, session)
        return {"status": "success"}

    @staticmethod
    async def _payment_succeeded(
        provider_name: str, data: dict[str, Any], session: AsyncSession
    ) -> dict[str, Any]:
        subscription_id = data.get("provider_subscription_id")
        if not subscription_id:
            return {"status": "success", "message": "Non-subscription payment"}
        subscription = await PaymentWebhookService._find_subscription(
            provider_name, subscription_id, session
        )
        if subscription is None:
            return {"status": "not_found"}
        if data.get("billing_reason") == "subscription_create":
            return {"status": "success", "message": "Initial subscription payment"}
        await SubscriptionService.renew_subscription(
            subscription.user_id,
            session,
            provider_payment_id=data.get("provider_payment_id"),
            provider_period_end=PaymentWebhookService._period_end(data.get("current_period_end")),
        )
        return {"status": "success"}

    @staticmethod
    async def _payment_failed(
        provider_name: str, data: dict[str, Any], _session: AsyncSession
    ) -> dict[str, Any]:
        logger.warning(
            "Payment failed through %s for subscription %s",
            provider_name,
            data.get("provider_subscription_id"),
        )
        return {"status": "success"}

    @staticmethod
    async def _checkout_completed(
        _provider_name: str, data: dict[str, Any], _session: AsyncSession
    ) -> dict[str, Any]:
        if not data.get("user_id"):
            return {"status": "ignored", "reason": "missing user metadata"}
        return {
            "status": "success",
            "user_id": data["user_id"],
            "plan_id": data.get("plan_id"),
        }

    @staticmethod
    async def _find_subscription(
        provider_name: str,
        provider_subscription_id: str | None,
        session: AsyncSession,
    ) -> UserSubscription | None:
        if not provider_subscription_id:
            return None
        return await session.scalar(
            select(UserSubscription).where(
                UserSubscription.provider_name == provider_name,
                UserSubscription.provider_subscription_id == provider_subscription_id,
            )
        )

    @staticmethod
    def _period_end(timestamp: int | float | None) -> datetime | None:
        """Convert a provider-normalized Unix timestamp to the DB's naive UTC."""
        if timestamp is None:
            return None
        return datetime.fromtimestamp(timestamp, UTC).replace(tzinfo=None)
