"""Comprehensive API endpoint tests to maximize test coverage across backend routes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.services.creator_seed import seed_creator_profile

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# GET /ready
# ---------------------------------------------------------------------------


async def test_ready_endpoint(client: AsyncClient):
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /chat/send-with-voice
# ---------------------------------------------------------------------------


async def test_chat_send_with_voice(client: AsyncClient, auth_headers: dict):
    mock_audio_resp = MagicMock()
    mock_audio_resp.audio_data = b"fake audio bytes"
    mock_audio_resp.audio_format = "mp3"

    mock_adapter = MagicMock()
    mock_adapter.synthesize_speech = AsyncMock(return_value=mock_audio_resp)

    with (
        patch(
            "app.services.voice.voice_adapter_builder.get_voice_adapter", return_value=mock_adapter
        ),
        patch(
            "app.services.chat.get_ai_client",
            return_value=MagicMock(
                send_message=AsyncMock(return_value=("Voice chat response", 15, "mock"))
            ),
        ),
    ):
        response = await client.post(
            "/chat/send-with-voice",
            json={"content": "Hello voice"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_message"] == "Hello voice"
        assert data["assistant_message"] == "Voice chat response"
        assert "audio" in data
        assert data["audio"]["format"] == "mp3"


async def test_chat_send_with_voice_empty_content(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/chat/send-with-voice",
        json={"content": "   "},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_chat_history_endpoint(client: AsyncClient, auth_headers: dict):
    response = await client.get("/chat/history?limit=10&offset=0", headers=auth_headers)
    assert response.status_code == 200
    assert "messages" in response.json()


async def test_chat_conversation_endpoint(client: AsyncClient, auth_headers: dict):
    response = await client.get("/chat/", headers=auth_headers)
    assert response.status_code == 200
    assert "id" in response.json()


# ---------------------------------------------------------------------------
# /memories Endpoints
# ---------------------------------------------------------------------------


async def test_memories_crud_flow(client: AsyncClient, auth_headers: dict):
    # 1. Create public memory (auto-approved)
    create_res = await client.post(
        "/memories",
        json={"content": "I live in Tokyo"},
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["is_auto_approved"] is True
    memory_id = created_data["memory"]["id"]

    # 2. List approved memories
    list_res = await client.get("/memories", headers=auth_headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(m["id"] == memory_id for m in list_data["memories"])

    # 3. Create sensitive memory (pending)
    sens_res = await client.post(
        "/memories",
        json={"content": "My personal email is test@domain.com"},
        headers=auth_headers,
    )
    assert sens_res.status_code == 201
    sens_data = sens_res.json()
    pending_id = sens_data["memory"]["id"]

    # 4. List pending memories
    pending_res = await client.get("/memories/pending", headers=auth_headers)
    assert pending_res.status_code == 200
    assert any(m["id"] == pending_id for m in pending_res.json()["memories"])

    # 5. Approve pending memory
    appr_res = await client.post(
        f"/memories/{pending_id}/approve",
        json={"approved": True},
        headers=auth_headers,
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["is_approved"] is True

    # 6. Reject pending memory
    sens_res2 = await client.post(
        "/memories",
        json={"content": "My phone is 9998887776"},
        headers=auth_headers,
    )
    pending_id2 = sens_res2.json()["memory"]["id"]
    rej_res = await client.post(
        f"/memories/{pending_id2}/approve",
        json={"approved": False},
        headers=auth_headers,
    )
    assert rej_res.status_code == 204

    # 7. Delete approved memory
    del_res = await client.delete(f"/memories/{memory_id}", headers=auth_headers)
    assert del_res.status_code == 204

    # 8. Get memory stats
    stats_res = await client.get("/memories/stats", headers=auth_headers)
    assert stats_res.status_code == 200
    assert stats_res.json()["total"] >= 2


# ---------------------------------------------------------------------------
# /tasks Endpoints
# ---------------------------------------------------------------------------


async def test_tasks_crud_flow(client: AsyncClient, auth_headers: dict):
    # 1. Create task (no trailing slash to avoid 307)
    create_res = await client.post(
        "/tasks",
        json={"title": "Buy groceries", "description": "Milk and eggs", "priority": "high"},
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    task_id = create_res.json()["id"]

    # 2. Get active tasks
    list_res = await client.get("/tasks", headers=auth_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. Update task
    upd_res = await client.patch(
        f"/tasks/{task_id}",
        json={"title": "Buy groceries and fruit"},
        headers=auth_headers,
    )
    assert upd_res.status_code == 200
    assert upd_res.json()["title"] == "Buy groceries and fruit"

    # 4. Complete task
    comp_res = await client.post(f"/tasks/{task_id}/complete", headers=auth_headers)
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "completed"

    # 5. Get task stats
    stats_res = await client.get("/tasks/stats", headers=auth_headers)
    assert stats_res.status_code == 200
    assert stats_res.json()["completed"] >= 1

    # 6. Delete task
    del_res = await client.delete(f"/tasks/{task_id}", headers=auth_headers)
    assert del_res.status_code == 204


# ---------------------------------------------------------------------------
# /subscriptions Endpoints
# ---------------------------------------------------------------------------


async def test_subscriptions_endpoints(client: AsyncClient, auth_headers: dict):
    # List plans (requires auth)
    plans_res = await client.get("/subscriptions/plans", headers=auth_headers)
    assert plans_res.status_code == 200
    assert len(plans_res.json()["plans"]) >= 3

    # Get current user subscription
    my_sub_res = await client.get("/subscriptions/me", headers=auth_headers)
    assert my_sub_res.status_code in (200, 404)

    # Upgrade subscription
    upgrade_res = await client.post(
        "/subscriptions/upgrade",
        json={"plan_id": "pro"},
        headers=auth_headers,
    )
    assert upgrade_res.status_code == 200
    assert upgrade_res.json()["plan_id"] == "pro"

    # Get stats
    stats_res = await client.get("/subscriptions/stats", headers=auth_headers)
    assert stats_res.status_code == 200

    # Cancel subscription
    cancel_res = await client.post(
        "/subscriptions/cancel",
        json={"reason": "Testing cancellation"},
        headers=auth_headers,
    )
    assert cancel_res.status_code == 200


# ---------------------------------------------------------------------------
# /voices Endpoints
# ---------------------------------------------------------------------------


async def test_voices_endpoints(client: AsyncClient, auth_headers: dict):
    # List system voices
    sys_res = await client.get("/voices/system", headers=auth_headers)
    assert sys_res.status_code == 200

    # List user voices
    user_res = await client.get("/voices/", headers=auth_headers)
    assert user_res.status_code == 200
    assert "voices" in user_res.json()


# ---------------------------------------------------------------------------
# /creator Endpoints
# ---------------------------------------------------------------------------


async def test_creator_endpoints(client: AsyncClient, auth_headers: dict, test_session):
    # Seed profile directly first to ensure DB record exists
    await seed_creator_profile(test_session)

    # Get profile
    prof_res = await client.get("/creator/profile")
    assert prof_res.status_code == 200
    assert prof_res.json()["name"] == "Vishal Singh Kushwaha"

    # Generate story
    story_res = await client.post(
        "/creator/story",
        json={"user_tone": "warm"},
        headers=auth_headers,
    )
    assert story_res.status_code == 200
    assert "story" in story_res.json()


# ---------------------------------------------------------------------------
# /webhooks Endpoints
# ---------------------------------------------------------------------------


async def test_stripe_webhook_invalid_signature(client: AsyncClient):
    res = await client.post(
        "/webhooks/stripe",
        content=b"{}",
        headers={"stripe-signature": "invalid_sig"},
    )
    assert res.status_code in (400, 422, 500)
