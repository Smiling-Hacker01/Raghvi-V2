"""Tests for 1-Click Google OAuth 2.0 integration and Gmail REST API sync."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.services.google_oauth_service import GoogleOAuthService


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


@pytest.fixture
async def auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    signup = await client.post(
        "/auth/signup",
        json={
            "username": f"oauth_user_{uuid4().hex[:6]}",
            "email": f"oauth_{uuid4().hex[:6]}@example.com",
            "password": "Password123!",
        },
    )
    assert signup.status_code == 201
    return {"Authorization": f"Bearer {signup.json()['access_token']}"}


def test_google_oauth_state_hmac_tamper_proofing() -> None:
    """Verify that generated OAuth states cannot be forged or tampered with."""
    user_id = str(uuid4())
    state = GoogleOAuthService.create_oauth_state(user_id, "Personal Gmail")

    # 1. Valid state decodes correctly
    extracted_user, label = GoogleOAuthService.verify_oauth_state(state)
    assert extracted_user == user_id
    assert label == "Personal Gmail"

    # 2. Tampered state raises ValueError
    tampered_state = state[:-4] + "xxxx"
    with pytest.raises(ValueError):
        GoogleOAuthService.verify_oauth_state(tampered_state)


@pytest.mark.asyncio
async def test_get_google_oauth_authorize_url(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Test generating 1-click Google OAuth authorize URL."""
    resp = await client.get(
        "/connected-accounts/oauth/google/authorize?account_label=My%20Work%20Gmail",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "accounts.google.com/o/oauth2/v2/auth" in data["authorization_url"]
    assert "gmail.readonly" in data["authorization_url"]
    assert "gmail.send" in data["authorization_url"]
    assert "state" in data
    assert "configured" in data


@pytest.mark.asyncio
async def test_google_oauth_callback_invalid_state_rejected(client: httpx.AsyncClient) -> None:
    """Test that forged or invalid state in callback returns 400 Bad Request."""
    url = "/connected-accounts/oauth/google/callback?code=test_code&state=invalid_forged_state"
    resp = await client.get(url)
    assert resp.status_code == 400
    assert "Invalid OAuth state" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_connect_google_oauth_account_and_sync(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Test connecting a Google OAuth account and syncing emails via simulated Gmail REST API."""
    mock_tokens = {
        "access_token": "ya29.mock_access_token",
        "refresh_token": "1//mock_refresh_token_xyz",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "https://www.googleapis.com/auth/gmail.readonly",
    }
    mock_userinfo = {
        "email": "vishal.google@gmail.com",
        "name": "Vishal Kushwaha",
    }

    with (
        patch.object(
            GoogleOAuthService, "exchange_auth_code", new_callable=AsyncMock
        ) as mock_exchange,
        patch.object(
            GoogleOAuthService, "get_google_userinfo", new_callable=AsyncMock
        ) as mock_info,
    ):
        mock_exchange.return_value = mock_tokens
        mock_info.return_value = mock_userinfo

        # Exchange code for connected account
        exchange_resp = await client.post(
            "/connected-accounts/oauth/google/exchange",
            json={
                "auth_code": "mock_google_auth_code_12345",
                "account_label": "One-Click Google",
            },
            headers=auth_headers,
        )

        assert exchange_resp.status_code == 200
        account_data = exchange_resp.json()
        assert account_data["provider"] == "gmail"
        assert account_data["identifier"] == "vishal.google@gmail.com"
        assert account_data["account_label"] == "One-Click Google"
        assert account_data["is_primary"] is True

        account_id = account_data["id"]

        # Now test sync on this OAuth account
        with patch.object(
            GoogleOAuthService, "sync_emails_via_gmail_api", new_callable=AsyncMock
        ) as mock_sync:
            from app.models.communication import CommunicationItem

            mock_sync.return_value = [
                CommunicationItem(
                    user_id="user_123",
                    channel="email",
                    sender="hr@google.com",
                    sender_name="Google HR",
                    recipient="vishal.google@gmail.com",
                    subject="Welcome to Google Cloud",
                    body="Your cloud onboarding package is ready.",
                )
            ]

            sync_resp = await client.post(
                f"/connected-accounts/{account_id}/sync",
                headers=auth_headers,
            )
            assert sync_resp.status_code == 200
            sync_data = sync_resp.json()
            assert sync_data["status"] == "success"
            assert sync_data["synced_count"] == 1
            assert "Google 1-Click Sync" in sync_data["message"]
