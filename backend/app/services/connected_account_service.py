"""Connected account service — multi-account credential management and sync."""

import base64
import json
import logging
import os
from typing import Any
from uuid import UUID

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.base import get_utc_now
from app.models.connected_account import ConnectedAccount
from app.schemas.connected_account import (
    ConnectedAccountCreate,
    ConnectedAccountResponse,
    ConnectedAccountUpdate,
    ProviderPresetResponse,
    SyncAccountResult,
)

logger = logging.getLogger(__name__)

# Provider default presets for rapid one-click connection
PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "gmail": {
        "name": "Google Gmail / Google Workspace",
        "account_type": "email",
        "default_imap_host": "imap.gmail.com",
        "default_imap_port": 993,
        "default_smtp_host": "smtp.gmail.com",
        "default_smtp_port": 465,
        "requires_app_password": True,
        "help_text": (
            "Use your Gmail address and a 16-character Google App Password "
            "(Google Account > Security > 2-Step Verification > App passwords)."
        ),
    },
    "outlook": {
        "name": "Microsoft Outlook / Office 365 / Hotmail",
        "account_type": "email",
        "default_imap_host": "outlook.office365.com",
        "default_imap_port": 993,
        "default_smtp_host": "smtp.office365.com",
        "default_smtp_port": 587,
        "requires_app_password": True,
        "help_text": "Use your Outlook/Office 365 email and account password or App Password.",
    },
    "yahoo": {
        "name": "Yahoo Mail",
        "account_type": "email",
        "default_imap_host": "imap.mail.yahoo.com",
        "default_imap_port": 993,
        "default_smtp_host": "smtp.mail.yahoo.com",
        "default_smtp_port": 465,
        "requires_app_password": True,
        "help_text": "Use your Yahoo email address and Yahoo App Password.",
    },
    "icloud": {
        "name": "Apple iCloud Mail",
        "account_type": "email",
        "default_imap_host": "imap.mail.me.com",
        "default_imap_port": 993,
        "default_smtp_host": "smtp.mail.me.com",
        "default_smtp_port": 587,
        "requires_app_password": True,
        "help_text": "Use your Apple ID email and an Apple App-Specific Password.",
    },
    "custom_imap": {
        "name": "Custom Corporate / University IMAP",
        "account_type": "email",
        "default_imap_host": None,
        "default_imap_port": 993,
        "default_smtp_host": None,
        "default_smtp_port": 465,
        "requires_app_password": False,
        "help_text": "Enter your organization's custom IMAP/SMTP server hostnames and credentials.",
    },
    "whatsapp_companion": {
        "name": "WhatsApp Android Companion",
        "account_type": "whatsapp",
        "default_imap_host": None,
        "default_imap_port": None,
        "default_smtp_host": None,
        "default_smtp_port": None,
        "requires_app_password": False,
        "help_text": (
            "Zero config needed. Real WhatsApp messages are synced seamlessly via the "
            "Android Notification Listener for WhatsApp or WhatsApp Business."
        ),
    },
    "whatsapp_cloud": {
        "name": "Meta WhatsApp Cloud API",
        "account_type": "whatsapp",
        "default_imap_host": None,
        "default_imap_port": None,
        "default_smtp_host": None,
        "default_smtp_port": None,
        "requires_app_password": False,
        "help_text": (
            "Attach your Meta Cloud API Phone Number ID and permanent system access token."
        ),
    },
}


class ConnectedAccountService:
    """Handles multi-user, multi-account registration, encrypted credentials, and syncing."""

    # -------------------------------------------------------------------------
    # 1. Cryptographic Isolation (AES-256-GCM per User)
    # -------------------------------------------------------------------------

    @staticmethod
    def _derive_encryption_key(user_id: str) -> bytes:
        """Derive an isolated 256-bit AES-GCM key bound to the user's ID."""
        settings = get_settings()
        master_secret = settings.jwt_secret_key.encode("utf-8")
        salt = user_id.encode("utf-8")

        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b"raghvi-connected-accounts-encryption-v1",
        )
        return hkdf.derive(master_secret)

    @classmethod
    def encrypt_credentials(cls, user_id: str, credentials: dict[str, Any]) -> str:
        """Encrypt credential dictionary using AES-256-GCM.

        Returns a base64 encoded string containing: nonce (12 bytes) + ciphertext_with_tag.
        """
        if not credentials:
            return ""

        key = cls._derive_encryption_key(user_id)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        plaintext_bytes = json.dumps(credentials).encode("utf-8")

        ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)
        payload = nonce + ciphertext
        return base64.b64encode(payload).decode("utf-8")

    @classmethod
    def decrypt_credentials(cls, user_id: str, encrypted_b64: str) -> dict[str, Any]:
        """Decrypt AES-256-GCM encrypted credentials back into a dictionary."""
        if not encrypted_b64:
            return {}

        try:
            key = cls._derive_encryption_key(user_id)
            aesgcm = AESGCM(key)
            raw = base64.b64decode(encrypted_b64.encode("utf-8"))
            if len(raw) < 13:
                return {}

            nonce = raw[:12]
            ciphertext = raw[12:]
            decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
            return json.loads(decrypted_bytes.decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to decrypt credentials for user {user_id}: {e}")
            return {}

    # -------------------------------------------------------------------------
    # 2. Presets and Metadata
    # -------------------------------------------------------------------------

    @staticmethod
    def get_presets() -> list[ProviderPresetResponse]:
        """Return list of provider auto-configuration presets."""
        presets = []
        for provider_key, info in PROVIDER_PRESETS.items():
            presets.append(
                ProviderPresetResponse(
                    provider=provider_key,
                    name=info["name"],
                    account_type=info["account_type"],
                    default_imap_host=info["default_imap_host"],
                    default_imap_port=info["default_imap_port"],
                    default_smtp_host=info["default_smtp_host"],
                    default_smtp_port=info["default_smtp_port"],
                    requires_app_password=info["requires_app_password"],
                    help_text=info["help_text"],
                )
            )
        return presets

    # -------------------------------------------------------------------------
    # 3. Account Management (CRUD)
    # -------------------------------------------------------------------------

    @classmethod
    async def create_account(
        cls,
        user_id: str,
        data: ConnectedAccountCreate,
        session: AsyncSession,
    ) -> ConnectedAccount:
        """Register a new email or messaging account for the user."""
        creds = dict(data.credentials)

        # Apply preset server hosts/ports if missing
        preset = PROVIDER_PRESETS.get(data.provider)
        if preset and data.account_type == "email":
            if "imap_host" not in creds and preset.get("default_imap_host"):
                creds["imap_host"] = preset["default_imap_host"]
            if "imap_port" not in creds and preset.get("default_imap_port"):
                creds["imap_port"] = preset["default_imap_port"]
            if "smtp_host" not in creds and preset.get("default_smtp_host"):
                creds["smtp_host"] = preset["default_smtp_host"]
            if "smtp_port" not in creds and preset.get("default_smtp_port"):
                creds["smtp_port"] = preset["default_smtp_port"]

        encrypted_creds = cls.encrypt_credentials(user_id, creds)

        # If marked primary, unset other primaries of the same account_type
        if data.is_primary:
            await session.execute(
                update(ConnectedAccount)
                .where(
                    and_(
                        ConnectedAccount.user_id == str(user_id),
                        ConnectedAccount.account_type == data.account_type,
                    )
                )
                .values(is_primary=False)
            )

        account = ConnectedAccount(
            user_id=str(user_id),
            account_type=data.account_type,
            provider=data.provider,
            account_label=data.account_label,
            identifier=data.identifier,
            encrypted_credentials=encrypted_creds,
            is_primary=data.is_primary,
            is_active=True,
            sync_interval_minutes=data.sync_interval_minutes,
        )
        session.add(account)
        await session.commit()
        await session.refresh(account)
        return account

    @staticmethod
    async def list_accounts(
        user_id: str,
        account_type: str | None = None,
        session: AsyncSession = None,
    ) -> list[ConnectedAccount]:
        """List all connected accounts belonging to this user."""
        filters = [ConnectedAccount.user_id == str(user_id)]
        if account_type:
            filters.append(ConnectedAccount.account_type == account_type)

        stmt = (
            select(ConnectedAccount)
            .where(and_(*filters))
            .order_by(ConnectedAccount.is_primary.desc(), ConnectedAccount.created_at.desc())
        )
        result = await session.scalars(stmt)
        return list(result.all())

    @staticmethod
    async def get_account(
        user_id: str,
        account_id: UUID | str,
        session: AsyncSession,
    ) -> ConnectedAccount | None:
        """Fetch a specific connected account ensuring user ownership."""
        target_uuid = UUID(str(account_id)) if not isinstance(account_id, UUID) else account_id
        stmt = select(ConnectedAccount).where(
            and_(
                ConnectedAccount.id == target_uuid,
                ConnectedAccount.user_id == str(user_id),
            )
        )
        return await session.scalar(stmt)

    @classmethod
    async def update_account(
        cls,
        user_id: str,
        account_id: UUID | str,
        data: ConnectedAccountUpdate,
        session: AsyncSession,
    ) -> ConnectedAccount | None:
        """Update an existing account's metadata or credentials."""
        account = await cls.get_account(user_id, account_id, session)
        if not account:
            return None

        if data.account_label is not None:
            account.account_label = data.account_label
        if data.is_active is not None:
            account.is_active = data.is_active
        if data.sync_interval_minutes is not None:
            account.sync_interval_minutes = data.sync_interval_minutes

        if data.is_primary is True:
            await session.execute(
                update(ConnectedAccount)
                .where(
                    and_(
                        ConnectedAccount.user_id == str(user_id),
                        ConnectedAccount.account_type == account.account_type,
                    )
                )
                .values(is_primary=False)
            )
            account.is_primary = True
        elif data.is_primary is False:
            account.is_primary = False

        if data.credentials is not None:
            # Merge with existing credentials
            existing_creds = cls.decrypt_credentials(user_id, account.encrypted_credentials or "")
            existing_creds.update(data.credentials)
            account.encrypted_credentials = cls.encrypt_credentials(user_id, existing_creds)

        await session.commit()
        await session.refresh(account)
        return account

    @classmethod
    async def delete_account(
        cls,
        user_id: str,
        account_id: UUID | str,
        session: AsyncSession,
    ) -> bool:
        """Delete a connected account."""
        account = await cls.get_account(user_id, account_id, session)
        if not account:
            return False

        await session.delete(account)
        await session.commit()
        return True

    # -------------------------------------------------------------------------
    # 4. Multi-Account Email Synchronization
    # -------------------------------------------------------------------------

    @classmethod
    async def sync_account(
        cls,
        user_id: str,
        account_id: UUID | str,
        session: AsyncSession,
        limit: int = 15,
    ) -> SyncAccountResult:
        """Synchronize emails from a specific user-connected account."""
        from app.services.communication_service import CommunicationService

        account = await cls.get_account(user_id, account_id, session)
        if not account:
            return SyncAccountResult(
                account_id=str(account_id),
                account_label="Unknown",
                synced_count=0,
                status="error",
                message="Account not found or access denied.",
            )

        if not account.is_active:
            return SyncAccountResult(
                account_id=str(account.id),
                account_label=account.account_label,
                synced_count=0,
                status="skipped",
                message="Account is inactive.",
            )

        if account.account_type != "email":
            return SyncAccountResult(
                account_id=str(account.id),
                account_label=account.account_label,
                synced_count=0,
                status="skipped",
                message=f"Sync not applicable for {account.account_type} account.",
            )

        creds = cls.decrypt_credentials(user_id, account.encrypted_credentials or "")

        # ── 1. Check if connected via Google OAuth 2.0 ───────────────────────
        if creds.get("auth_type") == "oauth2" or creds.get("refresh_token"):
            from app.services.google_oauth_service import GoogleOAuthService

            try:
                synced = await GoogleOAuthService.sync_emails_via_gmail_api(
                    user_id=str(user_id),
                    account_id=account.id,
                    account_label=account.account_label,
                    refresh_token=creds["refresh_token"],
                    session=session,
                    limit=limit,
                )
                account.last_synced_at = get_utc_now()
                await session.commit()
                return SyncAccountResult(
                    account_id=str(account.id),
                    account_label=account.account_label,
                    synced_count=len(synced),
                    status="success",
                    message=(
                        f"Synced {len(synced)} emails for {account.account_label} "
                        "via Google 1-Click Sync."
                    ),
                )
            except Exception as e:
                logger.error(f"Google OAuth sync error: {e}")
                return SyncAccountResult(
                    account_id=str(account.id),
                    account_label=account.account_label,
                    synced_count=0,
                    status="error",
                    message=f"Google 1-Click sync failed: {str(e)}",
                )

        # ── 2. Standard IMAP credentials fallback ─────────────────────────────
        preset = PROVIDER_PRESETS.get(account.provider, {})
        imap_host = creds.get("imap_host") or preset.get("default_imap_host")
        imap_port = creds.get("imap_port") or preset.get("default_imap_port", 993)
        email_user = creds.get("username", account.identifier)
        email_password = creds.get("password")

        if not email_password:
            return SyncAccountResult(
                account_id=str(account.id),
                account_label=account.account_label,
                synced_count=0,
                status="error",
                message="No credentials configured for this account.",
            )

        try:
            synced = await CommunicationService.sync_real_emails_via_imap(
                user_id=str(user_id),
                session=session,
                imap_host=imap_host,
                imap_port=imap_port,
                email_user=email_user,
                email_password=email_password,
                limit=limit,
                account_id=account.id,
                account_label=account.account_label,
            )
        except Exception as e:
            error_str = str(e)
            if "AUTHENTICATIONFAILED" in error_str:
                error_msg = (
                    "Authentication failed: Invalid credentials. For Gmail/Google Workspace, "
                    "Google requires a 16-character App Password (not account login password). "
                    "Or use Google 1-Click OAuth to connect without passwords. "
                    "Generate App Password at: https://myaccount.google.com/apppasswords"
                )
            else:
                error_msg = f"Failed to connect to mail server: {error_str}"
            return SyncAccountResult(
                account_id=str(account.id),
                account_label=account.account_label,
                synced_count=0,
                status="error",
                message=error_msg,
            )

        account.last_synced_at = get_utc_now()
        await session.commit()

        return SyncAccountResult(
            account_id=str(account.id),
            account_label=account.account_label,
            synced_count=len(synced),
            status="success",
            message=f"Synced {len(synced)} emails for {account.account_label}.",
        )

    @classmethod
    async def sync_all_accounts(
        cls,
        user_id: str,
        session: AsyncSession,
        limit: int = 15,
    ) -> list[SyncAccountResult]:
        """Synchronize all active email accounts for this user."""
        accounts = await cls.list_accounts(user_id=user_id, account_type="email", session=session)
        results = []
        for acc in accounts:
            if acc.is_active:
                res = await cls.sync_account(user_id, acc.id, session=session, limit=limit)
                results.append(res)
        return results

    @staticmethod
    def to_response(account: ConnectedAccount) -> ConnectedAccountResponse:
        """Convert ORM model to sanitized response (no secrets)."""
        return ConnectedAccountResponse(
            id=str(account.id),
            account_type=account.account_type,
            provider=account.provider,
            account_label=account.account_label,
            identifier=account.identifier,
            is_primary=account.is_primary,
            is_active=account.is_active,
            sync_interval_minutes=account.sync_interval_minutes,
            last_synced_at=account.last_synced_at.isoformat() if account.last_synced_at else None,
            created_at=account.created_at.isoformat(),
            updated_at=account.updated_at.isoformat(),
        )

    @classmethod
    async def connect_google_oauth(
        cls,
        user_id: str,
        email: str,
        tokens: dict[str, Any],
        account_label: str = "Personal Gmail",
        session: AsyncSession = None,
    ) -> ConnectedAccount:
        """Create or update a connected account using 1-click Google OAuth credentials."""
        accounts = await cls.list_accounts(user_id=user_id, account_type="email", session=session)
        existing = next(
            (
                a
                for a in accounts
                if a.identifier.lower() == email.lower()
                and (
                    cls.decrypt_credentials(user_id, a.encrypted_credentials or "").get("auth_type")
                    == "oauth2"
                    or a.account_label == account_label
                )
            ),
            None,
        )
        if not existing:
            existing = next((a for a in accounts if a.identifier.lower() == email.lower()), None)

        creds = {
            "auth_type": "oauth2",
            "provider": "google",
            "email": email,
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "token_type": tokens.get("token_type", "Bearer"),
            "expires_in": tokens.get("expires_in"),
            "scope": tokens.get("scope"),
        }

        if existing:
            existing_creds = cls.decrypt_credentials(user_id, existing.encrypted_credentials or "")
            if not creds.get("refresh_token") and existing_creds.get("refresh_token"):
                creds["refresh_token"] = existing_creds["refresh_token"]
            existing.encrypted_credentials = cls.encrypt_credentials(user_id, creds)
            existing.is_active = True
            existing.account_label = account_label
            await session.commit()
            await session.refresh(existing)
            return existing

        return await cls.create_account(
            user_id=user_id,
            data=ConnectedAccountCreate(
                account_type="email",
                provider="gmail",
                account_label=account_label,
                identifier=email,
                credentials=creds,
                is_primary=True,
                sync_interval_minutes=15,
            ),
            session=session,
        )
