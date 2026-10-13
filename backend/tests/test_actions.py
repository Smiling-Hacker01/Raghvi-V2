"""Tests for safe Android action proposals (M6)."""

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


async def test_action_propose_confirm_cancel_lifecycle(client: httpx.AsyncClient) -> None:
    # 1. Signup user
    signup = await client.post(
        "/auth/signup",
        json={
            "username": "actionuser",
            "email": "actionuser@example.com",
            "password": "super-secret-password",
        },
    )
    assert signup.status_code == 201
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    # 2. Test unsupported action rejection
    bad_action = await client.post(
        "/actions/propose",
        headers=headers,
        json={"action_type": "delete_all_files", "parameters": {}},
    )
    assert bad_action.status_code == 422

    # 3. Test parameter validation (invalid email)
    bad_email = await client.post(
        "/actions/propose",
        headers=headers,
        json={
            "action_type": "draft_email",
            "parameters": {"recipient": "not-an-email", "subject": "Hi"},
        },
    )
    assert bad_email.status_code == 422

    # 4. Propose valid draft_email action
    prop_res = await client.post(
        "/actions/propose",
        headers=headers,
        json={
            "action_type": "draft_email",
            "parameters": {
                "recipient": "colleague@example.com",
                "subject": "Project Status Update",
                "body": "Here is the summary of sprint progress.",
            },
            "description": "Draft email to colleague",
        },
    )
    assert prop_res.status_code == 201
    prop_data = prop_res.json()
    prop_id = prop_data["id"]
    assert prop_data["status"] == "awaiting_confirmation"

    # 5. Confirm action
    confirm_res = await client.post(
        f"/actions/{prop_id}/confirm",
        headers=headers,
        json={"confirmed": True},
    )
    assert confirm_res.status_code == 200
    assert confirm_res.json()["status"] == "confirmed"
    assert confirm_res.json()["confirmed_at"] is not None

    # 6. Re-confirming should be rejected (status is already confirmed)
    reconfirm = await client.post(
        f"/actions/{prop_id}/confirm",
        headers=headers,
        json={"confirmed": True},
    )
    assert reconfirm.status_code == 400

    # 7. Propose and cancel an open_maps action
    maps_prop = await client.post(
        "/actions/propose",
        headers=headers,
        json={
            "action_type": "open_maps",
            "parameters": {"destination": "San Francisco, CA"},
        },
    )
    assert maps_prop.status_code == 201
    maps_id = maps_prop.json()["id"]

    cancel_res = await client.post(
        f"/actions/{maps_id}/confirm",
        headers=headers,
        json={"confirmed": False},
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"


async def test_cross_user_action_isolation(client: httpx.AsyncClient) -> None:
    # User 1
    u1 = await client.post(
        "/auth/signup",
        json={"username": "user1", "email": "u1@example.com", "password": "password123"},
    )
    h1 = {"Authorization": f"Bearer {u1.json()['access_token']}"}

    # User 2
    u2 = await client.post(
        "/auth/signup",
        json={"username": "user2", "email": "u2@example.com", "password": "password123"},
    )
    h2 = {"Authorization": f"Bearer {u2.json()['access_token']}"}

    # User 1 creates proposal
    p1 = await client.post(
        "/actions/propose",
        headers=h1,
        json={"action_type": "open_app", "parameters": {"package_name": "com.example.calendar"}},
    )
    assert p1.status_code == 201
    p1_id = p1.json()["id"]

    # User 2 attempts to view User 1's proposal -> 404
    forbidden_get = await client.get(f"/actions/{p1_id}", headers=h2)
    assert forbidden_get.status_code == 404

    # User 2 attempts to confirm User 1's proposal -> 404
    forbidden_confirm = await client.post(
        f"/actions/{p1_id}/confirm",
        headers=h2,
        json={"confirmed": True},
    )
    assert forbidden_confirm.status_code == 404
