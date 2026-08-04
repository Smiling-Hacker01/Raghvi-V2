"""Unit tests for SubscriptionService."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.subscription import SubscriptionPlan
from app.services.subscription_service import SubscriptionService


@pytest.fixture
async def test_session():
    """Create test database session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Seed test plans
        plans = [
            SubscriptionPlan(
                id="free",
                name="Free",
                description="Free plan",
                price_usd=0.0,
                max_custom_voices=0,
            ),
            SubscriptionPlan(
                id="pro",
                name="Pro",
                description="Pro plan",
                price_usd=9.99,
                max_custom_voices=1,
            ),
        ]

        for plan in plans:
            session.add(plan)

        await session.commit()

        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_list_plans(test_session):
    """Test listing subscription plans."""
    plans = await SubscriptionService.list_plans(test_session)

    assert len(plans) == 2
    assert plans[0].id in ["free", "pro"]
    assert plans[0].price_usd in [0.0, 9.99]


@pytest.mark.asyncio
async def test_get_subscription_plan(test_session):
    """Test getting a specific plan."""
    plan = await SubscriptionService.get_subscription_plan("pro", test_session)

    assert plan is not None
    assert plan.id == "pro"
    assert plan.name == "Pro"
    assert plan.price_usd == 9.99
    assert plan.max_custom_voices == 1


@pytest.mark.asyncio
async def test_create_subscription(test_session):
    """Test creating a subscription."""
    user_id = "test_user_1"

    subscription = await SubscriptionService.create_subscription(
        user_id=user_id,
        plan_id="pro",
        session=test_session,
    )

    assert subscription is not None
    assert subscription.user_id == user_id
    assert subscription.plan_id == "pro"
    assert subscription.is_active is True
    assert subscription.expires_at > datetime.now(UTC).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_get_user_subscription(test_session):
    """Test retrieving user subscription."""
    user_id = "test_user_2"

    # Create subscription
    await SubscriptionService.create_subscription(
        user_id=user_id,
        plan_id="pro",
        session=test_session,
    )

    # Retrieve subscription
    subscription = await SubscriptionService.get_user_subscription(user_id, test_session)

    assert subscription is not None
    assert subscription.user_id == user_id
    assert subscription.plan_id == "pro"


@pytest.mark.asyncio
async def test_upgrade_subscription(test_session):
    """Test upgrading an existing subscription."""
    user_id = "test_user_3"

    # Create initial subscription
    await SubscriptionService.create_subscription(
        user_id=user_id,
        plan_id="free",
        session=test_session,
    )

    # Upgrade to pro
    upgraded = await SubscriptionService.create_subscription(
        user_id=user_id,
        plan_id="pro",
        session=test_session,
    )

    assert upgraded.plan_id == "pro"
    assert upgraded.renewed_at is not None


@pytest.mark.asyncio
async def test_cancel_subscription(test_session):
    """Test cancelling a subscription."""
    user_id = "test_user_4"

    # Create subscription
    await SubscriptionService.create_subscription(
        user_id=user_id,
        plan_id="pro",
        session=test_session,
    )

    # Cancel
    await SubscriptionService.cancel_subscription(user_id, test_session)

    # Verify cancelled
    subscription = await SubscriptionService.get_user_subscription(user_id, test_session)

    assert subscription is None  # get_user_subscription filters out inactive


@pytest.mark.asyncio
async def test_subscription_stats(test_session):
    """Test getting subscription statistics."""
    user_id = "test_user_5"

    # Create subscription
    await SubscriptionService.create_subscription(
        user_id=user_id,
        plan_id="pro",
        session=test_session,
    )

    # Get stats
    stats = await SubscriptionService.get_subscription_stats(user_id, test_session)

    assert stats["plan_id"] == "pro"
    assert stats["plan_name"] == "Pro"
    assert stats["is_active"] is True
    assert stats["voice_slots_available"] == 1
    assert stats["voice_slots_used"] == 0


@pytest.mark.asyncio
async def test_subscription_expiration_check(test_session):
    """Test expiration property."""
    user_id = "test_user_6"

    # Create expired subscription
    subscription = await SubscriptionService.create_subscription(
        user_id=user_id,
        plan_id="pro",
        session=test_session,
    )

    # Manually set to expired
    subscription.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    await test_session.commit()

    # Refresh
    await test_session.refresh(subscription)

    assert subscription.is_expired is True
    assert subscription.days_remaining == 0
