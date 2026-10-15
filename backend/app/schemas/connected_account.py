"""Schemas for multi-user and multi-account email and messaging connections."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ConnectedAccountCreate(BaseModel):
    """Payload to connect a new email or messaging account."""

    account_type: Literal["email", "whatsapp"]
    provider: str = Field(
        ...,
        description="Provider code: gmail, outlook, yahoo, icloud, custom_imap, whatsapp",
    )
    account_label: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="User-friendly label: Work Email, Personal Gmail, WhatsApp Business",
    )
    identifier: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Email address or phone number identifier",
    )
    credentials: dict[str, Any] = Field(
        default_factory=dict,
        description="Credential dictionary (e.g., password/app password, host, port, token)",
    )
    is_primary: bool = Field(
        default=False, description="Whether this is the user's default/primary account"
    )
    sync_interval_minutes: int = Field(default=15, ge=1, le=1440)


class ConnectedAccountUpdate(BaseModel):
    """Payload to update an existing connected account."""

    account_label: str | None = Field(default=None, min_length=1, max_length=100)
    is_primary: bool | None = None
    is_active: bool | None = None
    sync_interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    credentials: dict[str, Any] | None = None


class ConnectedAccountResponse(BaseModel):
    """Sanitized account response (credentials are strictly excluded)."""

    id: str
    account_type: str
    provider: str
    account_label: str
    identifier: str
    is_primary: bool
    is_active: bool
    sync_interval_minutes: int
    last_synced_at: str | None = None
    created_at: str
    updated_at: str


class ProviderPresetResponse(BaseModel):
    """Preconfigured server host, port, and security settings for easy user connection."""

    provider: str
    name: str
    account_type: str
    default_imap_host: str | None = None
    default_imap_port: int | None = None
    default_smtp_host: str | None = None
    default_smtp_port: int | None = None
    requires_app_password: bool = True
    help_text: str


class SyncAccountResult(BaseModel):
    """Result of synchronizing an account."""

    account_id: str
    account_label: str
    synced_count: int
    status: str
    message: str


class GoogleOAuthAuthorizeResponse(BaseModel):
    """1-Click Google OAuth authorization URL response."""

    authorization_url: str
    state: str
    configured: bool
    instructions: str | None = None


class GoogleOAuthExchangeRequest(BaseModel):
    """Request to exchange an OAuth auth_code from mobile or frontend for access."""

    auth_code: str = Field(..., description="Google authorization code from OAuth consent screen")
    account_label: str = Field(default="Personal Gmail", min_length=1, max_length=100)
    redirect_uri: str | None = Field(
        default=None, description="Redirect URI matching client request"
    )
