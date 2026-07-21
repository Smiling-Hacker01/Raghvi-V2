"""Pytest fixtures for backend tests."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models.user import User
from app.security.password import hash_password

# Test database URL (use SQLite for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    """Create test database and tables."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    yield async_session

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def override_get_db(test_db):
    """Override get_db_session dependency."""

    async def get_test_db():
        async with test_db() as session:
            yield session

    return get_test_db


@pytest.fixture
def app_with_test_db(override_get_db):
    """Create app with test database."""
    app.dependency_overrides[get_db_session] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def mock_ai_client():
    """Mock the AI client so tests don't hit real LLM APIs."""
    fake_client = MagicMock()
    fake_client.send_message = AsyncMock(
        return_value=("Hello! I'm Raghvi, how can I help you?", 42, "mock")
    )

    with patch("app.services.chat.get_ai_client", return_value=fake_client):
        yield fake_client


@pytest.fixture
async def client(app_with_test_db, mock_ai_client):
    """Create test HTTP client."""
    transport = ASGITransport(app=app_with_test_db)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def test_user(test_db):
    """Create a test user in the database."""
    async with test_db() as session:
        user = User(
            username="testuser",
            email="testuser@example.com",
            password_hash=hash_password("TestPassword123"),
            name="Test User",
            phone="1234567890",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest.fixture
async def auth_headers(client, test_user):
    """Get authorization headers with valid JWT token."""
    response = await client.post(
        "/auth/login",
        json={
            "username": "testuser",
            "password": "TestPassword123",
        },
    )

    assert response.status_code == 200

    token = response.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}",
    }


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
