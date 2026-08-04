"""Pytest configuration and shared fixtures."""

import asyncio
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.subscription import SubscriptionPlan
from app.models.user import User


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db_engine():
    """Create test database engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def test_session(test_db_engine) -> AsyncGenerator[AsyncSession]:
    """Create test database session with seeded data."""
    async_session = sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        # Seed subscription plans
        plans = [
            SubscriptionPlan(
                id="free",
                name="Free",
                description="Free plan",
                price_usd=0.0,
                max_custom_voices=0,
                supported_languages="en",
            ),
            SubscriptionPlan(
                id="pro",
                name="Pro",
                description="Pro plan",
                price_usd=9.99,
                max_custom_voices=1,
                supported_languages="en,hi",
            ),
            SubscriptionPlan(
                id="premium",
                name="Premium",
                description="Premium plan",
                price_usd=19.99,
                max_custom_voices=3,
                supported_languages="en,hi",
            ),
        ]

        for plan in plans:
            session.add(plan)

        await session.commit()

        yield session


@pytest.fixture
def test_db(test_db_engine):
    """Create test database session factory (callable fixture)."""
    from contextlib import asynccontextmanager

    from sqlalchemy import select

    @asynccontextmanager
    async def _session_factory():
        async_session = sessionmaker(
            test_db_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with async_session() as session:
            # Seed subscription plans only if they don't exist
            existing = await session.scalar(select(SubscriptionPlan).limit(1))
            if not existing:
                plans = [
                    SubscriptionPlan(
                        id="free",
                        name="Free",
                        description="Free plan",
                        price_usd=0.0,
                        max_custom_voices=0,
                        supported_languages="en",
                    ),
                    SubscriptionPlan(
                        id="pro",
                        name="Pro",
                        description="Pro plan",
                        price_usd=9.99,
                        max_custom_voices=1,
                        supported_languages="en,hi",
                    ),
                    SubscriptionPlan(
                        id="premium",
                        name="Premium",
                        description="Premium plan",
                        price_usd=19.99,
                        max_custom_voices=3,
                        supported_languages="en,hi",
                    ),
                ]

                for plan in plans:
                    session.add(plan)

                await session.commit()
            yield session

    return _session_factory


@pytest.fixture
async def user(test_session):
    """Create a test user."""
    from app.security.password import hash_password

    user = User(
        id="550e8400-e29b-41d4-a716-446655440000",
        username="testuser",
        email="test@example.com",
        password_hash=hash_password("TestPassword123"),
        name="Test User",
        phone="1234567890",
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest.fixture
async def test_user(user):
    """Alias for user fixture (for backward compatibility)."""
    return user


@pytest.fixture
async def client():
    """Create test HTTP client."""
    from collections.abc import AsyncGenerator

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select

    from app.db.session import get_db_session
    from app.main import app

    # Create test engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_db_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            # Seed subscription plans only if they don't exist
            from app.models.subscription import SubscriptionPlan

            existing = await session.scalar(select(SubscriptionPlan).limit(1))
            if not existing:
                plans = [
                    SubscriptionPlan(
                        id="free",
                        name="Free",
                        description="Free plan",
                        price_usd=0.0,
                        max_custom_voices=0,
                        supported_languages="en",
                    ),
                    SubscriptionPlan(
                        id="pro",
                        name="Pro",
                        description="Pro plan",
                        price_usd=9.99,
                        max_custom_voices=1,
                        supported_languages="en,hi",
                    ),
                    SubscriptionPlan(
                        id="premium",
                        name="Premium",
                        description="Premium plan",
                        price_usd=19.99,
                        max_custom_voices=3,
                        supported_languages="en,hi",
                    ),
                ]

                for plan in plans:
                    session.add(plan)

                await session.commit()
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def auth_headers(client):
    """Create authenticated user and return auth headers."""

    # Register user
    signup_response = await client.post(
        "/auth/signup",
        json={
            "email": "testuser@example.com",
            "username": "testuser",
            "password": "TestPassword123",
            "name": "Test User",
            "phone": "1234567890",
        },
    )

    assert signup_response.status_code == 201
    tokens = signup_response.json()

    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def mock_current_user():
    """Mock authenticated user."""
    return User(
        id="test_user_123",
        email="test@example.com",
        username="testuser",
    )


@pytest.fixture
def test_settings():
    """Override settings for testing."""
    from app.core.config import Settings

    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret_key="test_secret_key",
        stripe_api_key="sk_test_123",
        stripe_webhook_secret="whsec_test_123",
        elevenlabs_api_key="test_elevenlabs_key",
        s3_bucket="test-bucket",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


# Mock services for testing


class MockS3Service:
    """Mock S3 service for testing."""

    async def upload_voice_sample(
        self, user_id: str, voice_id: str, audio_data, file_extension: str = "wav"
    ) -> str:
        """Mock upload that returns fake URL."""
        return f"https://test-bucket.s3.amazonaws.com/voices/{user_id}/{voice_id}.{file_extension}"

    async def delete_voice_sample(self, s3_url: str) -> bool:
        """Mock delete."""
        return True

    async def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> str:
        """Mock presigned URL."""
        return f"https://test-bucket.s3.amazonaws.com/{s3_key}?signed=true"


@pytest.fixture
def mock_s3_service():
    """Provide mock S3 service."""
    return MockS3Service()


class MockStripe:
    """Mock Stripe client for testing."""

    @staticmethod
    def verify_signature(payload: bytes, sig_header: str, secret: str):
        """Mock signature verification."""
        return True

    @staticmethod
    def create_checkout_session(params: dict):
        """Mock checkout session creation."""
        return {
            "id": "cs_test_123",
            "url": "https://checkout.stripe.com/pay/cs_test_123",
        }


@pytest.fixture
def mock_stripe():
    """Provide mock Stripe client."""
    return MockStripe()


# Test data factories


def create_test_user(user_id: str = "test_user") -> dict:
    """Create test user data."""
    return {
        "id": user_id,
        "email": f"{user_id}@example.com",
        "username": user_id,
    }


def create_test_subscription(user_id: str, plan_id: str = "pro") -> dict:
    """Create test subscription data."""
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    return {
        "user_id": user_id,
        "plan_id": plan_id,
        "started_at": now,
        "expires_at": now + timedelta(days=30),
        "is_active": True,
    }


def create_test_voice(user_id: str, voice_name: str = "Test Voice") -> dict:
    """Create test voice data."""
    return {
        "user_id": user_id,
        "voice_type": "custom",
        "voice_id": "test_voice_id",
        "voice_name": voice_name,
        "provider": "elevenlabs",
        "languages": "en",
    }
