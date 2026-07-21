"""Chat endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.chat import (
    ChatSendRequest,
    ChatSendResponse,
    ChatHistoryResponse,
    ConversationResponse,
    ChatMessageResponse,
)
from app.services.ai.prompt import get_error_response
from app.services.chat import ChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Type aliases
CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("/send", response_model=ChatSendResponse)
async def send_message(
    request: ChatSendRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> ChatSendResponse:
    """Send a message to Raghvi and get response.

    Protected endpoint (requires valid JWT token).
    Orchestrates: message storage, LLM calling, response generation.

    Args:
        request: ChatSendRequest with user message
        current_user: Current authenticated user (from JWT)
        session: Database session

    Returns:
        ChatSendResponse with user_message, assistant_message, tokens_used

    Raises:
        HTTPException 401: If token invalid/expired
        HTTPException 500: If all LLM providers fail
    """
    if not request.content.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty",
        )

    user_id = current_user.id

    try:
        # Call chat service (handles all orchestration)
        result = await ChatService.send_message(
            user_id=user_id,
            user_message_content=request.content,
            session=session,
        )

        return ChatSendResponse(**result)

    except ValueError as e:
        # Configuration/validation error
        logger.error(f"Chat validation error for user {user_id}: {e}")
        # Return friendly error response
        return ChatSendResponse(
            user_message=request.content,
            assistant_message=get_error_response(),
            tokens_used=0,
        )

    except Exception as e:
        # LLM provider error (all failed)
        logger.error(f"Chat LLM error for user {user_id}: {e}")
        # Return friendly error response
        return ChatSendResponse(
            user_message=request.content,
            assistant_message=get_error_response(),
            tokens_used=0,
        )


@router.get("/", response_model=ConversationResponse)
async def get_conversation(
    current_user: CurrentUser,
    session: DbSession,
) -> ConversationResponse:
    """Get current conversation metadata.

    Protected endpoint (requires valid JWT token).

    Args:
        current_user: Current authenticated user
        session: Database session

    Returns:
        ConversationResponse with conversation metadata
    """
    try:
        conversation = await ChatService.get_or_create_conversation(current_user.id, session)
        message_count = await ChatService.get_conversation_message_count(conversation.id, session)

        return ConversationResponse(
            id=str(conversation.id),
            user_id=str(conversation.user_id),
            title=conversation.title,
            created_at=conversation.created_at.isoformat(),
            updated_at=conversation.updated_at.isoformat(),
            message_count=message_count,
        )
    except Exception as e:
        logger.error(f"Failed to get conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load conversation",
        )


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    limit: int = 20,
    offset: int = 0,
    current_user: CurrentUser = None,
    session: DbSession = None,
) -> ChatHistoryResponse:
    """Get conversation history (paginated).

    Protected endpoint (requires valid JWT token).
    Returns messages in chronological order (newest first).

    Args:
        limit: Max messages per page (default 20)
        offset: Pagination offset (default 0)
        current_user: Current authenticated user
        session: Database session

    Returns:
        ChatHistoryResponse with messages, total count, has_more flag
    """
    try:
        # TODO: Implement pagination and sorting
        # For now, this is a placeholder
        return ChatHistoryResponse(
            messages=[],
            total=0,
            has_more=False,
        )
    except Exception as e:
        logger.error(f"Failed to load chat history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load chat history",
        )
