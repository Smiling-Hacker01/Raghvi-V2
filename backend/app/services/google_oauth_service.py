"""Google OAuth 2.0 and Gmail REST API service for 1-click account synchronization."""

import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Any
from uuid import UUID

import aiohttp
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.communication import CommunicationItem

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GMAIL_MESSAGES_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"

GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]


class GoogleOAuthService:
    """Manages Google OAuth 2.0 authorization, token exchange, and Gmail REST API syncing."""

    # -------------------------------------------------------------------------
    # 1. State Signature and Verification (CSRF Protection)
    # -------------------------------------------------------------------------

    @staticmethod
    def create_oauth_state(user_id: str, account_label: str) -> str:
        """Create a tamper-proof HMAC-signed OAuth state parameter."""
        settings = get_settings()
        secret = settings.jwt_secret_key.encode("utf-8")
        timestamp = str(int(time.time()))

        raw_data = f"{user_id}:{account_label}:{timestamp}"
        sig = hmac.new(secret, raw_data.encode("utf-8"), hashlib.sha256).hexdigest()
        payload = f"{raw_data}:{sig}"
        return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")

    @staticmethod
    def verify_oauth_state(state: str) -> tuple[str, str]:
        """Verify HMAC-signed state and extract (user_id, account_label).

        Raises ValueError if invalid or expired (1 hour TTL).
        """
        settings = get_settings()
        secret = settings.jwt_secret_key.encode("utf-8")

        try:
            decoded = base64.urlsafe_b64decode(state.encode("utf-8")).decode("utf-8")
            parts = decoded.split(":")
            if len(parts) != 4:
                raise ValueError("Malformed state format")

            user_id, account_label, timestamp_str, sig = parts
            raw_data = f"{user_id}:{account_label}:{timestamp_str}"
            expected_sig = hmac.new(secret, raw_data.encode("utf-8"), hashlib.sha256).hexdigest()

            if not hmac.compare_digest(sig, expected_sig):
                raise ValueError("Invalid state signature")

            # Check expiry (max 1 hour)
            if int(time.time()) - int(timestamp_str) > 3600:
                raise ValueError("OAuth session state has expired")

            return user_id, account_label

        except Exception as e:
            logger.error(f"Failed to verify Google OAuth state: {e}")
            raise ValueError(f"Invalid OAuth state: {e}") from e

    # -------------------------------------------------------------------------
    # 2. Authorization URL
    # -------------------------------------------------------------------------

    @classmethod
    def get_authorization_url(
        cls,
        user_id: str,
        account_label: str = "Personal Gmail",
        redirect_uri: str | None = None,
    ) -> tuple[str, str, bool]:
        """Generate the Google 1-click consent URL.

        Returns: (authorization_url, state, is_configured)
        """
        settings = get_settings()
        client_id = settings.google_oauth_client_id
        configured = bool(client_id)
        effective_redirect = redirect_uri or settings.google_oauth_redirect_uri

        state = cls.create_oauth_state(user_id, account_label)

        params = {
            "client_id": client_id or "GOOGLE_CLIENT_ID_PLACEHOLDER",
            "redirect_uri": effective_redirect,
            "response_type": "code",
            "scope": " ".join(GOOGLE_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }

        query_string = urllib.parse.urlencode(params)
        auth_url = f"{GOOGLE_AUTH_URL}?{query_string}"
        return auth_url, state, configured

    # -------------------------------------------------------------------------
    # 3. Code Exchange & User Info
    # -------------------------------------------------------------------------

    @staticmethod
    async def exchange_auth_code(
        code: str,
        redirect_uri: str | None = None,
    ) -> dict[str, Any]:
        """Exchange authorization code for access_token and refresh_token."""
        settings = get_settings()
        client_id = settings.google_oauth_client_id
        client_secret = settings.google_oauth_client_secret
        effective_redirect = redirect_uri or settings.google_oauth_redirect_uri

        if not client_id or not client_secret:
            raise ValueError(
                "Google OAuth client credentials are not configured in backend settings. "
                "Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET."
            )

        payload = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": effective_redirect,
            "grant_type": "authorization_code",
        }

        async with (
            aiohttp.ClientSession() as session,
            session.post(GOOGLE_TOKEN_URL, data=payload) as resp,
        ):
            if resp.status != 200:
                text = await resp.text()
                logger.error(f"Google OAuth token exchange failed: {resp.status} {text}")
                raise ValueError(f"Google token exchange failed ({resp.status}): {text}")

            return await resp.json()

    @staticmethod
    async def get_google_userinfo(access_token: str) -> dict[str, Any]:
        """Retrieve user's email and profile details from Google UserInfo API."""
        headers = {"Authorization": f"Bearer {access_token}"}
        async with (
            aiohttp.ClientSession() as session,
            session.get(GOOGLE_USERINFO_URL, headers=headers) as resp,
        ):
            if resp.status != 200:
                text = await resp.text()
                logger.error(f"Failed to fetch Google userinfo: {resp.status} {text}")
                raise ValueError(f"Failed to fetch userinfo from Google ({resp.status})")

            return await resp.json()

    @staticmethod
    async def refresh_access_token(refresh_token: str) -> str:
        """Use refresh_token to acquire a fresh Google access_token."""
        settings = get_settings()
        client_id = settings.google_oauth_client_id
        client_secret = settings.google_oauth_client_secret

        if not client_id or not client_secret:
            raise ValueError("Google OAuth credentials missing for token refresh.")

        payload = {
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
        }

        async with (
            aiohttp.ClientSession() as session,
            session.post(GOOGLE_TOKEN_URL, data=payload) as resp,
        ):
            if resp.status != 200:
                text = await resp.text()
                logger.error(f"Failed to refresh Google token: {resp.status} {text}")
                raise ValueError(f"Failed to refresh Google token ({resp.status}): {text}")

            data = await resp.json()
            return data["access_token"]

    # -------------------------------------------------------------------------
    # 4. Gmail REST API Synchronization
    # -------------------------------------------------------------------------

    @classmethod
    async def sync_emails_via_gmail_api(
        cls,
        user_id: str,
        account_id: UUID | str,
        account_label: str,
        refresh_token: str,
        session: AsyncSession,
        limit: int = 15,
    ) -> list[CommunicationItem]:
        """Fetch real emails via Google Gmail REST API using OAuth2 refresh token."""
        access_token = await cls.refresh_access_token(refresh_token)
        headers = {"Authorization": f"Bearer {access_token}"}

        synced_items = []

        async with aiohttp.ClientSession() as http_client:
            # 1. Fetch message list
            list_params = {"maxResults": str(min(limit, 50)), "q": "in:inbox"}
            async with http_client.get(
                GMAIL_MESSAGES_URL, headers=headers, params=list_params
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise ValueError(f"Gmail messages list failed ({resp.status}): {text}")

                data = await resp.json()
                messages = data.get("messages", [])

            # 2. Fetch full message details for each
            for msg_meta in messages[:limit]:
                msg_id = msg_meta.get("id")
                if not msg_id:
                    continue

                msg_url = f"{GMAIL_MESSAGES_URL}/{msg_id}?format=full"
                async with http_client.get(msg_url, headers=headers) as msg_resp:
                    if msg_resp.status != 200:
                        continue

                    msg_data = await msg_resp.json()
                    headers_list = msg_data.get("payload", {}).get("headers", [])
                    header_map = {
                        h["name"].lower(): h["value"] for h in headers_list if "name" in h
                    }

                    subject = header_map.get("subject", "No Subject")
                    sender_raw = header_map.get("from", "unknown")
                    sender_name = (
                        sender_raw.split("<")[0].strip().strip('"')
                        if "<" in sender_raw
                        else sender_raw
                    )
                    recipient = header_map.get("to", "me")
                    thread_id = msg_data.get("threadId", msg_id)

                    # Extract body text from parts or snippet
                    snippet = msg_data.get("snippet", "")
                    body_text = snippet

                    # Try to extract plain text body from payload parts if present
                    parts = msg_data.get("payload", {}).get("parts", [])
                    for part in parts:
                        if part.get("mimeType") == "text/plain":
                            data_b64 = part.get("body", {}).get("data")
                            if data_b64:
                                try:
                                    body_text = base64.urlsafe_b64decode(data_b64).decode(
                                        "utf-8", errors="replace"
                                    )
                                    break
                                except Exception:
                                    pass

                    # Check if already saved
                    existing = await session.scalar(
                        select(CommunicationItem).where(
                            and_(
                                CommunicationItem.user_id == str(user_id),
                                CommunicationItem.thread_id == thread_id,
                            )
                        )
                    )

                    if not existing:
                        target_acc_id = (
                            account_id if isinstance(account_id, UUID) else UUID(str(account_id))
                        )
                        item = CommunicationItem(
                            user_id=str(user_id),
                            channel="email",
                            sender=sender_raw,
                            sender_name=sender_name,
                            recipient=recipient,
                            subject=subject,
                            body=body_text.strip() or snippet,
                            thread_id=thread_id,
                            account_id=target_acc_id,
                            account_label=account_label,
                            is_read=False,
                        )
                        session.add(item)
                        synced_items.append(item)

        await session.commit()
        return synced_items
