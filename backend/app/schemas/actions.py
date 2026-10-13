"""Action proposal schemas."""

from typing import Any

from pydantic import BaseModel, Field


class ActionProposalRequest(BaseModel):
    action_type: str = Field(..., description="Action type: draft_email, open_maps, open_app")
    parameters: dict[str, Any] = Field(default_factory=dict)
    description: str | None = Field(default=None)


class ActionConfirmationRequest(BaseModel):
    confirmed: bool = Field(..., description="True to execute/confirm, False to cancel")


class ActionProposalResponse(BaseModel):
    id: str
    user_id: str
    action_type: str
    parameters: dict[str, Any]
    status: str
    description: str | None = None
    expires_at: str
    created_at: str
    confirmed_at: str | None = None
