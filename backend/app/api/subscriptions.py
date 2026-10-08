"""Subscription and billing endpoints."""

import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.payments.adapter_builder import get_payment_provider
from app.payments.base import (
    CheckoutSessionRequest as ProviderCheckoutSessionRequest,
)
from app.payments.base import (
    PaymentProviderError,
)
from app.schemas.subscription import (
    CancelSubscriptionRequest,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    SubscriptionListResponse,
    SubscriptionPlanResponse,
    UserSubscriptionResponse,
)
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/plans", response_model=SubscriptionListResponse)
async def list_plans(
    current_user: CurrentUser,
    session: DbSession,
) -> SubscriptionListResponse:
    """Get all available subscription plans."""
    try:
        plans = await SubscriptionService.list_plans(session)

        # Get user's current plan
        user_sub = await SubscriptionService.get_user_subscription(current_user.id, session)
        current_plan = user_sub.plan_id if user_sub else None

        return SubscriptionListResponse(
            plans=[
                SubscriptionPlanResponse(
                    id=plan.id,
                    name=plan.name,
                    description=plan.description,
                    price_usd=plan.price_usd,
                    billing_cycle=plan.billing_cycle,
                    max_custom_voices=plan.max_custom_voices,
                    supported_languages=plan.supported_languages,
                    daily_message_limit=plan.daily_message_limit,
                    priority_support=plan.priority_support,
                    family_sharing_slots=plan.family_sharing_slots,
                )
                for plan in plans
            ],
            user_current_plan=current_plan,
        )

    except Exception as e:
        logger.error(f"Failed to list plans: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load plans",
        ) from e


@router.get("/me", response_model=UserSubscriptionResponse)
async def get_my_subscription(
    current_user: CurrentUser,
    session: DbSession,
) -> UserSubscriptionResponse:
    """Get current user's subscription."""
    try:
        subscription = await SubscriptionService.get_user_subscription(current_user.id, session)

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription",
            )

        plan = await SubscriptionService.get_subscription_plan(subscription.plan_id, session)

        return UserSubscriptionResponse(
            id=str(subscription.id),
            user_id=subscription.user_id,
            plan_id=subscription.plan_id,
            plan_name=plan.name if plan else "Unknown",
            started_at=subscription.started_at.isoformat(),
            expires_at=subscription.expires_at.isoformat(),
            is_active=subscription.is_active,
            is_expired=subscription.is_expired,
            days_remaining=subscription.days_remaining,
            auto_renew=subscription.auto_renew,
            provider_name=subscription.provider_name,
            provider_subscription_id=subscription.provider_subscription_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load subscription",
        ) from e


@router.post("/upgrade", response_model=CheckoutSessionResponse)
async def upgrade_subscription(
    request: CheckoutSessionRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> CheckoutSessionResponse:
    """Create a checkout session for an active paid plan."""
    try:
        plan = await SubscriptionService.get_subscription_plan(request.plan_id, session)
        if not plan or not plan.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
        if plan.price_usd <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The free plan does not require checkout",
            )
        existing_subscription = await SubscriptionService.get_user_subscription(
            current_user.id, session
        )
        if existing_subscription and existing_subscription.provider_subscription_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An active paid subscription already exists",
            )

        billing_cycle = {
            "monthly": "month",
            "yearly": "year",
            "annually": "year",
        }.get(plan.billing_cycle.lower(), plan.billing_cycle.lower())
        if billing_cycle not in {"day", "week", "month", "year"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported billing cycle for checkout",
            )
        amount_cents = int(
            (Decimal(str(plan.price_usd)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        provider = get_payment_provider()
        result = await provider.create_checkout_session(
            ProviderCheckoutSessionRequest(
                user_id=current_user.id,
                plan_id=request.plan_id,
                success_url=request.success_url,
                cancel_url=request.cancel_url,
                customer_email=current_user.email,
                metadata=request.metadata or {},
                amount_cents=amount_cents,
                billing_cycle=billing_cycle,
                plan_name=plan.name,
            )
        )
        return CheckoutSessionResponse(
            provider_name=provider.provider_name,
            session_id=result.session_id,
            checkout_url=result.url,
            expires_at=result.expires_at,
        )

    except HTTPException:
        raise
    except PaymentProviderError as e:
        logger.error(f"Payment error during upgrade: {e.provider}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to upgrade subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate upgrade",
        ) from e


@router.post("/cancel")
async def cancel_subscription(
    request: CancelSubscriptionRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> dict:
    """Cancel subscription."""
    try:
        subscription = await SubscriptionService.get_user_subscription(current_user.id, session)
        provider_subscription_id = subscription.provider_subscription_id if subscription else None
        if subscription and provider_subscription_id:
            provider_name = subscription.provider_name or "stripe"
            provider = get_payment_provider(provider_name)
            if not await provider.cancel_subscription(provider_subscription_id):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Payment provider could not cancel the subscription",
                )
        await SubscriptionService.cancel_subscription(current_user.id, session)

        return {
            "status": "cancelled",
            "message": "Subscription cancelled successfully",
        }

    except HTTPException:
        raise
    except PaymentProviderError as e:
        logger.error("Payment provider cancellation failed (%s): %s", e.provider, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to cancel subscription with payment provider",
        ) from e
    except ValueError as e:
        logger.error(f"Cancel error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription",
        ) from e


@router.get("/stats")
async def get_subscription_stats(
    current_user: CurrentUser,
    session: DbSession,
) -> dict:
    """Get subscription statistics."""
    try:
        stats = await SubscriptionService.get_subscription_stats(current_user.id, session)
        return stats

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load statistics",
        ) from e
