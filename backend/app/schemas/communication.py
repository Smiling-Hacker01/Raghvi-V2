"""Schemas for email, WhatsApp, and meeting communications."""

from pydantic import BaseModel, Field


class EmailItemResponse(BaseModel):
    """Email item representation."""

    id: str
    sender: str
    sender_name: str
    recipient: str
    subject: str | None = None
    body: str
    thread_id: str | None = None
    account_id: str | None = None
    account_label: str | None = None
    is_read: bool
    received_at: str


class WhatsAppItemResponse(BaseModel):
    """WhatsApp conversation message representation."""

    id: str
    sender: str
    sender_name: str
    recipient: str
    body: str
    account_id: str | None = None
    account_label: str | None = None
    is_read: bool
    received_at: str


class DraftReplyResponse(BaseModel):
    """Human-like contextual drafted reply."""

    draft_reply: str
    recipient: str
    channel: str
    context_summary: str


class DraftReplyRequest(BaseModel):
    """User instructions for drafting reply."""

    user_instructions: str | None = None


class ScheduleMeetingRequest(BaseModel):
    """Request to schedule meeting with invitations."""

    title: str = Field(..., min_length=1, max_length=200)
    date: str = Field(..., min_length=1)
    time: str = Field(..., min_length=1)
    attendees: list[str] = Field(default_factory=list)
    description: str | None = None
    auto_confirm: bool = Field(
        default=False,
        description="If True, immediately confirms proposal and dispatches invite emails to attendees.",
    )


class SeedCommunicationRequest(BaseModel):
    """Seed incoming email or WhatsApp message for testing/sync."""

    channel: str = Field(..., pattern="^(email|whatsapp)$")
    sender: str
    sender_name: str
    recipient: str = "vishal@raghvi.ai"
    subject: str | None = None
    body: str
    thread_id: str | None = None
    account_id: str | None = None
    account_label: str | None = None


class SyncRealEmailRequest(BaseModel):
    """Payload to trigger real IMAP sync with custom or env credentials."""

    imap_host: str | None = None
    imap_port: int | None = None
    email_user: str | None = None
    email_password: str | None = None
    limit: int = Field(default=10, ge=1, le=50)


class SendRealEmailRequest(BaseModel):
    """Payload to send real email through SMTP."""

    recipient: str
    subject: str
    body: str
    smtp_host: str | None = None
    smtp_port: int | None = None
    email_user: str | None = None
    email_password: str | None = None
