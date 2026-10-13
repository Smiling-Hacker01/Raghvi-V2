"""Tests for user lifecycle: data export and permanent account deletion (M7)."""

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


async def test_data_export_and_account_deletion_flow(client: httpx.AsyncClient) -> None:
    # 1. Register user
    signup = await client.post(
        "/auth/signup",
        json={
            "username": "exportuser",
            "email": "export@example.com",
            "password": "super-secret-password",
            "name": "Export Tester",
        },
    )
    assert signup.status_code == 201
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Add sample task and memory
    await client.post(
        "/tasks",
        headers=headers,
        json={"title": "Important privacy task", "priority": "high"},
    )
    await client.post(
        "/memories",
        headers=headers,
        json={"content": "Loves hiking and fresh air"},
    )

    # 3. Request data export
    export_res = await client.get("/users/export", headers=headers)
    assert export_res.status_code == 200
    export_data = export_res.json()

    assert export_data["export_version"] == "1.0"
    assert export_data["profile"]["username"] == "exportuser"
    assert export_data["profile"]["email"] == "export@example.com"
    assert len(export_data["tasks"]) == 1
    assert export_data["tasks"][0]["title"] == "Important privacy task"
    assert len(export_data["memories"]) == 1
    assert "hiking" in export_data["memories"][0]["content"]

    # 4. Request permanent account deletion
    delete_res = await client.delete("/users/me", headers=headers)
    assert delete_res.status_code == 204

    # 5. Subsequent access using the deleted user's token MUST be rejected
    rejected_me = await client.get("/auth/me", headers=headers)
    assert rejected_me.status_code == 401

    rejected_tasks = await client.get("/tasks", headers=headers)
    assert rejected_tasks.status_code == 401

    rejected_export = await client.get("/users/export", headers=headers)
    assert rejected_export.status_code == 401
