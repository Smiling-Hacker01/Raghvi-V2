"""Subscription service — business logic for plans and subscriptions."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import SubscriptionPlan, UserSubscription
from app.models.voice import UserVoice

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Manage user subscriptions and plans."""

    @staticmethod
    async def get_subscription_plan(
        plan_id: str,
        session: AsyncSession,
    ) -> SubscriptionPlan | None:
        """Get subscription plan by ID."""
        return await session.scalar(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))

    @staticmethod
    async def list_plans(session: AsyncSession) -> list[SubscriptionPlan]:
        """List all active subscription plans."""
        plans = await session.scalars(
            select(SubscriptionPlan)
            .where(SubscriptionPlan.is_active)
            .order_by(SubscriptionPlan.price_usd)
        )
        return plans.all()

    @staticmethod
    async def get_user_subscription(
        user_id: str,
        session: AsyncSession,
    ) -> UserSubscription | None:
        """Get user's current subscription."""
        return await session.scalar(
            select(UserSubscription).where(
                and_(
                    UserSubscription.user_id == user_id,
                    UserSubscription.is_active,
                )
            )
        )

    @staticmethod
    async def create_subscription(
        user_id: str,
        plan_id: str,
        stripe_subscription_id: str | None = None,
        stripe_customer_id: str | None = None,
        session: AsyncSession = None,
    ) -> UserSubscription:
        """Create or upgrade user subscription."""

        # Validate plan exists
        plan = await SubscriptionService.get_subscription_plan(plan_id, session)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")

        # Check if user already has active subscription
        existing = await SubscriptionService.get_user_subscription(user_id, session)
        if existing:
            # Upgrade existing subscription
            existing.plan_id = plan_id
            existing.renewed_at = datetime.now(UTC).replace(tzinfo=None)
            existing.expires_at = (datetime.now(UTC) + timedelta(days=30)).replace(tzinfo=None)
            existing.stripe_subscription_id = (
                stripe_subscription_id or existing.stripe_subscription_id
            )
            existing.stripe_customer_id = stripe_customer_id or existing.stripe_customer_id
            existing.updated_at = datetime.now(UTC).replace(tzinfo=None)

            await session.commit()
            logger.info(f"Subscription upgraded for user {user_id}: {plan_id}")
            return existing

        # Create new subscription
        expires_at = (datetime.now(UTC) + timedelta(days=30)).replace(tzinfo=None)

        subscription = UserSubscription(
            user_id=user_id,
            plan_id=plan_id,
            started_at=datetime.now(UTC).replace(tzinfo=None),
            expires_at=expires_at,
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=stripe_customer_id,
        )

        session.add(subscription)
        await session.commit()

        logger.info(f"Subscription created for user {user_id}: {plan_id}")

        return subscription

    @staticmethod
    async def renew_subscription(
        user_id: str,
        session: AsyncSession,
    ) -> UserSubscription:
        """Renew user's subscription."""

        subscription = await SubscriptionService.get_user_subscription(user_id, session)
        if not subscription:
            raise ValueError("No active subscription to renew")

        # Extend by 30 days
        subscription.expires_at = subscription.expires_at + timedelta(days=30)
        subscription.renewed_at = datetime.now(UTC).replace(tzinfo=None)
        subscription.updated_at = datetime.now(UTC).replace(tzinfo=None)

        await session.commit()

        logger.info(f"Subscription renewed for user {user_id}")

        return subscription

    @staticmethod
    async def cancel_subscription(
        user_id: str,
        session: AsyncSession,
    ) -> None:
        """Cancel user's subscription."""

        subscription = await SubscriptionService.get_user_subscription(user_id, session)
        if not subscription:
            raise ValueError("No active subscription to cancel")

        subscription.is_active = False
        subscription.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        subscription.updated_at = datetime.now(UTC).replace(tzinfo=None)

        # Expire all custom voices
        from app.services.voice.voice_service import VoiceService

        await VoiceService.expire_user_voices(user_id, session)

        await session.commit()

        logger.info(f"Subscription cancelled for user {user_id}")

    @staticmethod
    async def check_and_expire_subscriptions(session: AsyncSession) -> int:
        """
        Check for expired subscriptions and deactivate them.
        Call this from a scheduled job (daily).
        """

        now = datetime.now(UTC).replace(tzinfo=None)

        expired = await session.scalars(
            select(UserSubscription).where(
                and_(
                    UserSubscription.is_active,
                    UserSubscription.expires_at < now,
                )
            )
        )

        count = 0
        for subscription in expired.all():
            subscription.is_active = False
            subscription.updated_at = now
            count += 1

            logger.info(f"Subscription expired for user {subscription.user_id}")

            # Expire custom voices
            from app.services.voice.voice_service import VoiceService

            await VoiceService.expire_user_voices(subscription.user_id, session)

        if count > 0:
            await session.commit()

        logger.info(f"Expired {count} subscriptions")

        return count

    @staticmethod
    async def get_subscription_stats(
        user_id: str,
        session: AsyncSession,
    ) -> dict:
        """Get user's subscription stats."""

        subscription = await SubscriptionService.get_user_subscription(user_id, session)

        if not subscription:
            return {
                "plan_id": "free",
                "is_active": False,
                "days_remaining": 0,
                "voice_slots_used": 0,
                "voice_slots_available": 0,
            }

        plan = await SubscriptionService.get_subscription_plan(subscription.plan_id, session)

        # Count custom voices
        from sqlalchemy import func

        voice_count = (
            await session.scalar(
                select(func.count(UserVoice.id)).where(
                    and_(
                        UserVoice.user_id == user_id,
                        UserVoice.voice_type == "custom",
                        UserVoice.deleted_at.is_(None),
                    )
                )
            )
            or 0
        )

        return {
            "plan_id": subscription.plan_id,
            "plan_name": plan.name if plan else "Unknown",
            "is_active": subscription.is_active,
            "is_expired": subscription.is_expired,
            "days_remaining": subscription.days_remaining,
            "expires_at": subscription.expires_at.isoformat(),
            "voice_slots_used": voice_count,
            "voice_slots_available": plan.max_custom_voices if plan else 0,
            "auto_renew": subscription.auto_renew,
        }


def get_subscription_service() -> SubscriptionService:
    """Get subscription service instance."""
    return SubscriptionService()
