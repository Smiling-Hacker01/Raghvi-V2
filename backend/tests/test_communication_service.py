"""Tests for autonomous email search, contextual human replies, WhatsApp, and meetings."""

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
from app.models.communication import CommunicationItem
from app.services.communication_service import CommunicationService


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


def test_draft_human_email_reply_no_ai_giveaways() -> None:
    incoming = CommunicationItem(
        user_id="user_123",
        channel="email",
        sender="rahul@techcorp.com",
        sender_name="Rahul",
        recipient="vishal@raghvi.ai",
        subject="Project Timeline Update",
        body="Hey Vishal, could you please share an update on when the final draft will be ready?",
    )

    draft = CommunicationService.draft_human_email_reply(
        target_email=incoming,
        user_display_name="Vishal",
    )

    # Must be 100% human, NO AI giveaways
    assert "As an AI" not in draft
    assert "I hope this email finds you well" not in draft
    assert "assistant" not in draft.lower()
    assert "Hi Rahul," in draft
    assert "Best,\nVishal" in draft
    assert "tomorrow evening" in draft or "draft" in draft


def test_draft_human_whatsapp_reply_warm_and_natural() -> None:
    msg = CommunicationItem(
        user_id="user_123",
        channel="whatsapp",
        sender="+919876543210",
        sender_name="Priya",
        recipient="vishal",
        body="Kal shaam ko coffee chalenge kya?",
    )

    draft = CommunicationService.draft_human_whatsapp_reply([msg])

    # Must sound like a real person texting
    assert "AI" not in draft
    assert "assistant" not in draft.lower()
    assert "Haan" in draft or "milte" in draft or "done" in draft


def test_parse_communication_intent_detection() -> None:
    # 1. Meeting intent
    meet_intent = CommunicationService.parse_communication_intent(
        "Raghvi schedule meeting on Friday at 4 PM and invite rahul@tech.com"
    )
    assert meet_intent is not None
    assert meet_intent["type"] == "schedule_meeting"
    assert "rahul@tech.com" in meet_intent["attendees"]

    # 2. Email check
    mail_intent = CommunicationService.parse_communication_intent(
        "Raghvi check whether I have any new mail from Rahul"
    )
    assert mail_intent is not None
    assert mail_intent["type"] == "check_email"
    assert mail_intent["sender"] == "Rahul"

    # 3. WhatsApp check
    wa_intent = CommunicationService.parse_communication_intent("Raghvi check whatsapp from Priya")
    assert wa_intent is not None
    assert wa_intent["type"] == "check_whatsapp"
    assert wa_intent["sender"] == "Priya"


async def test_communications_full_api_workflow(client: httpx.AsyncClient) -> None:
    # 1. Signup user
    signup = await client.post(
        "/auth/signup",
        json={
            "username": f"comm_user_{uuid4().hex[:6]}",
            "email": f"comm_{uuid4().hex[:6]}@example.com",
            "password": "Password123!",
        },
    )
    assert signup.status_code == 201
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    # 2. Seed an email
    seed_email = await client.post(
        "/communications/seed",
        headers=headers,
        json={
            "channel": "email",
            "sender": "aman@company.com",
            "sender_name": "Aman",
            "subject": "Product Design Sync",
            "body": "Hi, are we meeting tomorrow to review the product design?",
            "thread_id": "thread_design_01",
        },
    )
    assert seed_email.status_code == 201
    email_id = seed_email.json()["id"]

    # 3. Seed WhatsApp message
    seed_wa = await client.post(
        "/communications/seed",
        headers=headers,
        json={
            "channel": "whatsapp",
            "sender": "+919811223344",
            "sender_name": "Simran",
            "body": "Kahan ho? Ready ho gaye?",
        },
    )
    assert seed_wa.status_code == 201

    # 4. Search email
    search_email = await client.get("/communications/emails?q=Product", headers=headers)
    assert search_email.status_code == 200
    assert len(search_email.json()) == 1
    assert search_email.json()[0]["sender_name"] == "Aman"

    # 5. Get full thread context
    thread_res = await client.get(f"/communications/emails/{email_id}/thread", headers=headers)
    assert thread_res.status_code == 200
    assert len(thread_res.json()) >= 1

    # 6. Draft completely human email reply
    draft_email_res = await client.post(
        f"/communications/emails/{email_id}/draft-reply",
        headers=headers,
        json={"user_instructions": "Yes, let's meet at 11 AM"},
    )
    assert draft_email_res.status_code == 200
    draft_email_data = draft_email_res.json()
    assert "Hi Aman," in draft_email_data["draft_reply"]
    assert "11 AM" in draft_email_data["draft_reply"]
    assert "AI" not in draft_email_data["draft_reply"]

    # 7. Check WhatsApp messages from Simran
    wa_list = await client.get("/communications/whatsapp?sender=Simran", headers=headers)
    assert wa_list.status_code == 200
    assert len(wa_list.json()) == 1
    assert wa_list.json()[0]["body"] == "Kahan ho? Ready ho gaye?"

    # 8. Draft human WhatsApp reply
    wa_draft_res = await client.post(
        "/communications/whatsapp/draft-reply?sender=Simran",
        headers=headers,
    )
    assert wa_draft_res.status_code == 200
    wa_draft_data = wa_draft_res.json()
    assert "AI" not in wa_draft_data["draft_reply"]
    assert "assistant" not in wa_draft_data["draft_reply"].lower()
    assert "nikal" in wa_draft_data["draft_reply"] or "minute" in wa_draft_data["draft_reply"]

    # 9. Schedule meeting
    sched_res = await client.post(
        "/communications/meetings/schedule",
        headers=headers,
        json={
            "title": "Quarterly Strategy Review",
            "date": "2026-10-20",
            "time": "15:00",
            "attendees": ["aman@company.com", "simran@work.com"],
        },
    )
    assert sched_res.status_code == 201
    assert sched_res.json()["status"] == "awaiting_confirmation"
    assert "Quarterly Strategy Review" in sched_res.json()["description"]
