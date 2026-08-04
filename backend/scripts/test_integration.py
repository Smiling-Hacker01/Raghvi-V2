"""Test database integration with subscription and voice systems."""

import asyncio

from sqlalchemy import func, select, text

from app.db.session import AsyncSessionLocal
from app.models.subscription import SubscriptionPlan, UserSubscription
from app.models.voice import SystemVoice, UserVoice
from app.services.subscription_service import SubscriptionService


async def test_db():
    """Test database integration."""

    async with AsyncSessionLocal() as session:
        # Test 1: Check subscription plans
        result = await session.execute(select(SubscriptionPlan))
        plans = result.scalars().all()
        print(f"✓ Found {len(plans)} subscription plans:")
        for plan in plans:
            print(f"  - {plan.name}: ${plan.price_usd} ({plan.max_custom_voices} voices)")

        # Test 2: Check tables exist
        result = await session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' AND "
                "(table_name LIKE '%subscription%' OR table_name LIKE '%voice%')"
            )
        )
        tables = result.scalars().all()
        print(f"\n✓ Subscription/Voice tables: {len(tables)}")
        for table in tables:
            print(f"  - {table}")

        # Test 3: Test SubscriptionService
        print("\n✓ Testing SubscriptionService...")
        plans = await SubscriptionService.list_plans(session)
        print(f"  - list_plans() returned {len(plans)} plans")

        # Test 4: Check table row counts
        user_subs_count = await session.scalar(select(func.count(UserSubscription.id)))
        user_voices_count = await session.scalar(select(func.count(UserVoice.id)))
        system_voices_count = await session.scalar(select(func.count(SystemVoice.id)))

        print("\n✓ Table statistics:")
        print(f"  - subscription_plans: {len(plans)} rows")
        print(f"  - user_subscriptions: {user_subs_count} rows")
        print(f"  - user_voices: {user_voices_count} rows")
        print(f"  - system_voices: {system_voices_count} rows")

        print("\n✓ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_db())
