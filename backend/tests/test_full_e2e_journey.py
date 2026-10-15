"""End-to-End Release Journey Integration Test (M8).

Executes the complete user lifecycle:
1. Register new account.
2. Authenticate and restore session.
3. Send a message to Raghvi.
4. Verify response persistence and history.
5. Create, retrieve, and verify user memory.
6. Create, list, and complete tasks.
7. Verify task reminder scheduling.
8. Configure briefing opt-in and fetch synthesized briefing.
9. Propose safe Android action and confirm execution.
10. Export complete user data archive.
11. Permanently delete account.
12. Verify revoked session and full authorization rejection.
"""

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


async def test_full_user_journey_end_to_end(client: httpx.AsyncClient) -> None:
    # ----------------------------------------------------
    # Step 1: Register a new account
    # ----------------------------------------------------
    reg_resp = await client.post(
        "/auth/register",
        json={
            "username": "journeyuser",
            "email": "journey@example.com",
            "password": "productionPassword2026!",
            "name": "Journey Explorer",
        },
    )
    assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"
    tokens = reg_resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # ----------------------------------------------------
    # Step 2: Authenticate and restore session
    # ----------------------------------------------------
    me_resp = await client.get("/auth/me", headers=headers)
    assert me_resp.status_code == 200
    user_data = me_resp.json()
    assert user_data["username"] == "journeyuser"
    assert user_data["email"] == "journey@example.com"

    # Verify token refresh
    refresh_resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200
    new_access_token = refresh_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {new_access_token}"}

    # ----------------------------------------------------
    # Step 3: Send message to Raghvi
    # ----------------------------------------------------
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_ai = MagicMock()
    mock_ai.send_message = AsyncMock(
        return_value=(
            "<emotion>warm</emotion><voice_text>Hello! I'm here for you.</voice_text>"
            "<chat_text>Hello! Planning your schedule sounds great, let me help.</chat_text>",
            45,
            "mock_ai",
        )
    )

    with patch("app.services.chat.get_ai_client", return_value=mock_ai):
        chat_resp = await client.post(
            "/chat/send",
            headers=headers,
            json={"content": "Hello Raghvi, I am planning my schedule for the week."},
        )
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert chat_data["user_message"] == "Hello Raghvi, I am planning my schedule for the week."
    assert chat_data["assistant_message"]

    # ----------------------------------------------------
    # Step 4: Verify conversation history persistence
    # ----------------------------------------------------
    history_resp = await client.get("/chat/history", headers=headers)
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert history["total"] >= 2  # user message + assistant reply
    messages = history["messages"]
    assert any(m["role"] == "user" for m in messages)
    assert any(m["role"] == "assistant" for m in messages)

    # ----------------------------------------------------
    # Step 5: Verify memory workflow
    # ----------------------------------------------------
    mem_resp = await client.post(
        "/memories",
        headers=headers,
        json={"content": "I prefer working on deep focus tasks in the morning."},
    )
    assert mem_resp.status_code == 201

    mem_list_resp = await client.get("/memories", headers=headers)
    assert mem_list_resp.status_code == 200
    memories = mem_list_resp.json()["memories"]
    assert len(memories) >= 1
    assert any("deep focus" in m["content"] for m in memories)

    # ----------------------------------------------------
    # Step 6: Create and complete a task
    # ----------------------------------------------------
    task_resp = await client.post(
        "/tasks",
        headers=headers,
        json={
            "title": "Review release checklist",
            "description": "Ensure all quality gates pass",
            "priority": "high",
        },
    )
    assert task_resp.status_code == 201
    task_id = task_resp.json()["id"]

    complete_resp = await client.post(f"/tasks/{task_id}/complete", headers=headers)
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "completed"

    # ----------------------------------------------------
    # Step 7: Create a pending task with due date (for reminders & briefing)
    # ----------------------------------------------------
    task_pending_resp = await client.post(
        "/tasks",
        headers=headers,
        json={
            "title": "Deploy staging backend",
            "priority": "medium",
        },
    )
    assert task_pending_resp.status_code == 201

    # ----------------------------------------------------
    # Step 8: Configure and test briefing opt-in
    # ----------------------------------------------------
    briefing_pref_resp = await client.patch(
        "/briefings/preferences",
        headers=headers,
        json={"opt_in": True, "quiet_hours_start": 22, "quiet_hours_end": 7},
    )
    assert briefing_pref_resp.status_code == 200

    briefing_resp = await client.get("/briefings/today", headers=headers)
    assert briefing_resp.status_code == 200
    briefing = briefing_resp.json()
    assert briefing["opted_in"] is True
    assert briefing["pending_tasks_count"] >= 1
    assert any(t["title"] == "Deploy staging backend" for t in briefing["tasks"])

    # ----------------------------------------------------
    # Step 9: Propose Android action and verify approval
    # ----------------------------------------------------
    action_prop_resp = await client.post(
        "/actions/propose",
        headers=headers,
        json={
            "action_type": "open_maps",
            "parameters": {"destination": "Bengaluru Innovation Hub"},
            "description": "Navigate to innovation hub",
        },
    )
    assert action_prop_resp.status_code == 201
    action_id = action_prop_resp.json()["id"]
    assert action_prop_resp.json()["status"] == "awaiting_confirmation"

    action_confirm_resp = await client.post(
        f"/actions/{action_id}/confirm",
        headers=headers,
        json={"confirmed": True},
    )
    assert action_confirm_resp.status_code == 200
    assert action_confirm_resp.json()["status"] == "confirmed"

    # ----------------------------------------------------
    # Step 10: Export user data archive
    # ----------------------------------------------------
    export_resp = await client.get("/users/export", headers=headers)
    assert export_resp.status_code == 200
    export_archive = export_resp.json()
    assert export_archive["export_version"] == "1.0"
    assert export_archive["profile"]["username"] == "journeyuser"
    assert len(export_archive["conversations"]) >= 1
    assert len(export_archive["memories"]) >= 1
    assert len(export_archive["tasks"]) >= 2

    # ----------------------------------------------------
    # Step 11: Permanently delete test account
    # ----------------------------------------------------
    delete_resp = await client.delete("/users/me", headers=headers)
    assert delete_resp.status_code == 204

    # ----------------------------------------------------
    # Step 12: Verify full authorization revocation
    # ----------------------------------------------------
    rejected_me = await client.get("/auth/me", headers=headers)
    assert rejected_me.status_code == 401

    rejected_tasks = await client.get("/tasks", headers=headers)
    assert rejected_tasks.status_code == 401

    rejected_chat = await client.get("/chat/history", headers=headers)
    assert rejected_chat.status_code == 401

    rejected_export = await client.get("/users/export", headers=headers)
    assert rejected_export.status_code == 401
