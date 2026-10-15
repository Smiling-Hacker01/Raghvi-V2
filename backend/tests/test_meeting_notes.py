"""Tests for meeting notes, transcription extraction, and lifecycle (Phase 8)."""

import os
from collections.abc import AsyncGenerator
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-thirty-two-bytes")

from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.services.meeting_service import MeetingService


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


def test_transcript_extraction_decisions_and_actions() -> None:
    transcript = (
        "Good morning team, let us review the sprint goals.\n"
        "We agreed to migrate the database schema to PostgreSQL by Friday.\n"
        "Decision: All endpoints must enforce JWT token authorization.\n"
        "Action item: implement rate limiter assigned to Rahul\n"
        "Todo: write comprehensive unit tests by Priya\n"
        "We also talked about frontend color themes and accessibility.\n"
        "Wrap up: sprint demo scheduled next Monday."
    )

    extracted = MeetingService.extract_notes_from_transcript(transcript)

    assert len(extracted["key_decisions"]) == 2
    assert "All endpoints must enforce JWT token authorization." in extracted["key_decisions"]
    assert len(extracted["action_items"]) == 2
    assert extracted["action_items"][0]["owner"] == "Rahul"
    assert extracted["action_items"][1]["owner"] == "Priya"
    assert extracted["confidence_score"] >= 0.9
    assert extracted["uncertainty_notes"] is None


def test_transcript_extraction_uncertainty_for_short_audio() -> None:
    transcript = "Quick sync done."
    extracted = MeetingService.extract_notes_from_transcript(transcript)

    assert extracted["confidence_score"] < 0.8
    assert extracted["uncertainty_notes"] is not None
    assert "nuances may be omitted" in extracted["uncertainty_notes"]


async def test_meeting_notes_crud_and_user_isolation(client: httpx.AsyncClient) -> None:
    # 1. Register User A
    user_a = await client.post(
        "/auth/signup",
        json={
            "username": f"user_a_{uuid4().hex[:6]}",
            "email": f"usera_{uuid4().hex[:6]}@example.com",
            "password": "Password123!",
        },
    )
    assert user_a.status_code == 201
    token_a = user_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. Register User B
    user_b = await client.post(
        "/auth/signup",
        json={
            "username": f"user_b_{uuid4().hex[:6]}",
            "email": f"userb_{uuid4().hex[:6]}@example.com",
            "password": "Password123!",
        },
    )
    assert user_b.status_code == 201
    token_b = user_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 3. User A creates a meeting note
    create_res = await client.post(
        "/meetings",
        headers=headers_a,
        json={
            "title": "Architecture Review",
            "transcript": (
                "Discussing Raghvi assistant pipeline.\n"
                "We finalized the voice pipeline architecture.\n"
                "Action item: review security posture assigned to Ankit\n"
            ),
            "duration_seconds": 1800,
        },
    )
    assert create_res.status_code == 201
    data = create_res.json()
    meeting_id = data["id"]
    assert data["title"] == "Architecture Review"
    assert len(data["key_decisions"]) >= 1
    assert len(data["action_items"]) == 1

    # 4. User B cannot access User A's meeting note
    unauth_get = await client.get(f"/meetings/{meeting_id}", headers=headers_b)
    assert unauth_get.status_code == 404

    # 5. User A retrieves meeting note
    get_res = await client.get(f"/meetings/{meeting_id}", headers=headers_a)
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Architecture Review"

    # 6. User A updates/corrects meeting note
    patch_res = await client.patch(
        f"/meetings/{meeting_id}",
        headers=headers_a,
        json={
            "title": "Architecture Review v2",
            "summary": "Updated summary with deeper architectural insights.",
        },
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Architecture Review v2"
    assert "deeper architectural insights" in patch_res.json()["summary"]

    # 7. Search meeting notes
    search_res = await client.get("/meetings?q=architectural", headers=headers_a)
    assert search_res.status_code == 200
    assert search_res.json()["total"] == 1

    # 8. Export markdown
    export_res = await client.get(f"/meetings/{meeting_id}/export", headers=headers_a)
    assert export_res.status_code == 200
    assert export_res.headers["content-type"].startswith("text/markdown")
    assert "# Meeting Notes: Architecture Review v2" in export_res.text
    assert "## Executive Summary" in export_res.text

    # 9. Delete meeting note (User B cannot delete)
    unauth_del = await client.delete(f"/meetings/{meeting_id}", headers=headers_b)
    assert unauth_del.status_code == 404

    del_res = await client.delete(f"/meetings/{meeting_id}", headers=headers_a)
    assert del_res.status_code == 204

    # 10. Subsequent GET returns 404 (soft-deleted)
    get_deleted = await client.get(f"/meetings/{meeting_id}", headers=headers_a)
    assert get_deleted.status_code == 404


async def test_meeting_notes_included_in_user_lifecycle(client: httpx.AsyncClient) -> None:
    signup = await client.post(
        "/auth/signup",
        json={
            "username": f"user_lc_{uuid4().hex[:6]}",
            "email": f"userlc_{uuid4().hex[:6]}@example.com",
            "password": "Password123!",
        },
    )
    assert signup.status_code == 201
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    # Create meeting note
    await client.post(
        "/meetings",
        headers=headers,
        json={
            "title": "Quarterly Planning",
            "transcript": "Decision: increase AI memory retention.\nTodo: update docs by dev",
        },
    )

    # Export user data
    export_res = await client.get("/users/export", headers=headers)
    assert export_res.status_code == 200
    export_data = export_res.json()
    assert "meeting_notes" in export_data
    assert len(export_data["meeting_notes"]) == 1
    assert export_data["meeting_notes"][0]["title"] == "Quarterly Planning"

    # Delete account
    del_res = await client.delete("/users/me", headers=headers)
    assert del_res.status_code == 204
