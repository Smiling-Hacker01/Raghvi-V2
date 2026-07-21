"""Chat-related request/response schemas."""

from pydantic import BaseModel, Field


class ChatSendRequest(BaseModel):
    """Request body for POST /chat/send."""

    content: str = Field(..., min_length=1, max_length=5000, description="User message content")


class ChatMessageResponse(BaseModel):
    """Individual message in chat history."""

    id: str
    role: str  # "user" or "assistant"
    content: str
    tokens_used: int | None = None
    created_at: str


class ChatSendResponse(BaseModel):
    """Response body for POST /chat/send."""

    user_message: str
    assistant_message: str
    tokens_used: int
    # Note: Never expose "provider_used" - that's internal only


class ChatHistoryResponse(BaseModel):
    """Response body for GET /chat/history."""

    messages: list[ChatMessageResponse]
    total: int
    has_more: bool


class ConversationResponse(BaseModel):
    """Response body for GET /chat/."""

    id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
