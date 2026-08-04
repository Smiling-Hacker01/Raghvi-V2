"""Stripe webhook handlers."""

import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict:
    """
    Handle Stripe webhook events.

    Stripe sends events for:
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_succeeded
    - invoice.payment_failed
    """
    settings = get_settings()

    # Get raw body for signature verification
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        logger.error("No Stripe signature header found")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No signature header",
        )

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.stripe_webhook_secret,
        )
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        ) from e
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        ) from e

    # Handle the event
    event_type = event["type"]
    data = event["data"]["object"]

    logger.info(f"Received Stripe webhook: {event_type}")

    try:
        if event_type == "customer.subscription.created":
            await handle_subscription_created(data, session)

        elif event_type == "customer.subscription.updated":
            await handle_subscription_updated(data, session)

        elif event_type == "customer.subscription.deleted":
            await handle_subscription_deleted(data, session)

        elif event_type == "invoice.payment_succeeded":
            await handle_payment_succeeded(data, session)

        elif event_type == "invoice.payment_failed":
            await handle_payment_failed(data, session)

        elif event_type == "checkout.session.completed":
            await handle_checkout_completed(data, session)

        else:
            logger.info(f"Unhandled event type: {event_type}")

    except Exception as e:
        logger.error(f"Error handling webhook {event_type}: {e}", exc_info=True)
        # Return 200 to prevent Stripe from retrying
        # Log error for manual investigation
        return {"status": "error_logged", "message": str(e)}

    return {"status": "success"}


async def handle_subscription_created(
    subscription_data: dict,
    session: AsyncSession,
) -> None:
    """Handle subscription.created event."""

    stripe_subscription_id = subscription_data["id"]
    stripe_customer_id = subscription_data["customer"]
    status_value = subscription_data["status"]

    # Get plan ID from metadata or subscription items
    plan_id = subscription_data.get("metadata", {}).get("plan_id", "pro")

    # Get user ID from customer metadata
    settings = get_settings()
    stripe.api_key = settings.stripe_api_key

    customer = stripe.Customer.retrieve(stripe_customer_id)
    user_id = customer.get("metadata", {}).get("user_id")

    if not user_id:
        logger.error(f"No user_id in customer metadata: {stripe_customer_id}")
        return

    # Calculate expiration (not used currently but kept for reference)

    # Create subscription
    if status_value == "active":
        await SubscriptionService.create_subscription(
            user_id=user_id,
            plan_id=plan_id,
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=stripe_customer_id,
            session=session,
        )

        logger.info(f"Subscription created for user {user_id}: {plan_id}")


async def handle_subscription_updated(
    subscription_data: dict,
    session: AsyncSession,
) -> None:
    """Handle subscription.updated event."""

    stripe_subscription_id = subscription_data["id"]
    status_value = subscription_data["status"]

    # Get user subscription by Stripe ID
    await session.execute(
        f"SELECT * FROM user_subscriptions "
        f"WHERE stripe_subscription_id = '{stripe_subscription_id}'"
    )

    # Update status based on Stripe status
    if status_value == "canceled":
        # Handle cancellation
        logger.info(f"Subscription cancelled: {stripe_subscription_id}")

    elif status_value == "past_due":
        # Handle payment failure
        logger.warning(f"Subscription past due: {stripe_subscription_id}")

    logger.info(f"Subscription updated: {stripe_subscription_id} -> {status_value}")


async def handle_subscription_deleted(
    subscription_data: dict,
    session: AsyncSession,
) -> None:
    """Handle subscription.deleted event."""

    stripe_subscription_id = subscription_data["id"]

    # Find user by Stripe subscription ID
    from sqlalchemy import select

    from app.models.subscription import UserSubscription

    subscription = await session.scalar(
        select(UserSubscription).where(
            UserSubscription.stripe_subscription_id == stripe_subscription_id
        )
    )

    if subscription:
        await SubscriptionService.cancel_subscription(subscription.user_id, session)
        logger.info(f"Subscription deleted for user {subscription.user_id}")
    else:
        logger.warning(f"Subscription not found: {stripe_subscription_id}")


async def handle_payment_succeeded(
    invoice_data: dict,
    session: AsyncSession,
) -> None:
    """Handle invoice.payment_succeeded event."""

    stripe_subscription_id = invoice_data.get("subscription")

    if not stripe_subscription_id:
        logger.info("Payment succeeded for non-subscription invoice")
        return

    # Find user subscription
    from sqlalchemy import select

    from app.models.subscription import UserSubscription

    subscription = await session.scalar(
        select(UserSubscription).where(
            UserSubscription.stripe_subscription_id == stripe_subscription_id
        )
    )

    if subscription:
        # Renew subscription
        await SubscriptionService.renew_subscription(subscription.user_id, session)
        logger.info(f"Payment succeeded, subscription renewed: {subscription.user_id}")
    else:
        logger.warning(f"Subscription not found for payment: {stripe_subscription_id}")


async def handle_payment_failed(
    invoice_data: dict,
    session: AsyncSession,
) -> None:
    """Handle invoice.payment_failed event."""

    stripe_subscription_id = invoice_data.get("subscription")

    if not stripe_subscription_id:
        return

    logger.warning(f"Payment failed for subscription: {stripe_subscription_id}")

    # TODO: Send email notification to user
    # TODO: Implement retry logic or grace period


async def handle_checkout_completed(
    session_data: dict,
    session: AsyncSession,
) -> None:
    """Handle checkout.session.completed event."""

    metadata = session_data.get("metadata", {})
    user_id = metadata.get("user_id")
    plan_id = metadata.get("plan_id", "pro")

    if not user_id:
        logger.error("No user_id in checkout session metadata")
        return

    logger.info(f"Checkout completed for user {user_id}: {plan_id}")

    # Subscription will be created by subscription.created event
    # This is just for logging/tracking
