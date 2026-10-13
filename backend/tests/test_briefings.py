"""Tests for proactive daily briefings (M5)."""

import os
from collections.abc import AsyncGenerator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-thirty-two-bytes")

from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.services.briefing_service import BriefingService


@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_db_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()
    await engine.dispose()


def test_quiet_hours_calculation():
    # 22 to 7 (crosses midnight)
    assert BriefingService.is_in_quiet_hours(23, quiet_start=22, quiet_end=7) is True
    assert BriefingService.is_in_quiet_hours(2, quiet_start=22, quiet_end=7) is True
    assert BriefingService.is_in_quiet_hours(6, quiet_start=22, quiet_end=7) is True
    assert BriefingService.is_in_quiet_hours(8, quiet_start=22, quiet_end=7) is False
    assert BriefingService.is_in_quiet_hours(14, quiet_start=22, quiet_end=7) is False

    # Within same day: e.g. 1 to 5
    assert BriefingService.is_in_quiet_hours(3, quiet_start=1, quiet_end=5) is True
    assert BriefingService.is_in_quiet_hours(12, quiet_start=1, quiet_end=5) is False


async def test_briefing_opt_in_flow(client: httpx.AsyncClient) -> None:
    # 1. Signup user
    signup = await client.post(
        "/auth/signup",
        json={
            "username": "briefinguser",
            "email": "briefing@example.com",
            "password": "super-secret-password",
            "name": "Briefing Tester",
        },
    )
    assert signup.status_code == 201
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Check initial briefing (disabled by default per M5 spec)
    res = await client.get("/briefings/today", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["opted_in"] is False
    assert "disabled" in data["summary"].lower()

    # 3. Update preferences to opt in
    pref_res = await client.patch(
        "/briefings/preferences",
        headers=headers,
        json={
            "opt_in": True,
            "quiet_hours_start": 23,
            "quiet_hours_end": 6,
            "morning_time": "08:30",
        },
    )
    assert pref_res.status_code == 200
    assert pref_res.json()["opt_in"] is True

    # 4. Add a task for user
    task_res = await client.post(
        "/tasks",
        headers=headers,
        json={"title": "Prepare portfolio release", "priority": "high"},
    )
    assert task_res.status_code == 201

    # 5. Fetch briefing with opt-in enabled
    briefing_res = await client.get("/briefings/today", headers=headers)
    assert briefing_res.status_code == 200
    briefing_data = briefing_res.json()
    assert briefing_data["opted_in"] is True
    assert briefing_data["pending_tasks_count"] == 1
    assert "Prepare portfolio release" in [t["title"] for t in briefing_data["tasks"]]
