"""Chat endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db_session
from app.models.message import Message
from app.models.user import User
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatMessageResponse,
    ChatSendRequest,
    ChatSendResponse,
    ConversationResponse,
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
    """Send message to Raghvi.
    
    Raghvi will:
    1. Retrieve your relevant memories for context
    2. Include them in the conversation
    3. Respond with personalized advice
    """
    # Extract user_id before try block (avoid lazy-load issues)
    user_id = str(current_user.id)
    
    if not request.content.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty",
        )
    
    try:
        result = await ChatService.send_message(
            user_id=user_id,
            user_message_content=request.content,
            session=session,
        )
        
        return ChatSendResponse(**result)
        
    except ValueError as e:
        logger.error(f"Chat validation error for user {user_id}: {e}")
        from app.services.ai.prompt import get_error_response
        return ChatSendResponse(
            user_message=request.content,
            assistant_message=get_error_response(),
            tokens_used=0,
        )
    
    except Exception as e:
        logger.error(f"Chat error for user {user_id}: {e}")
        await session.rollback()
        from app.services.ai.prompt import get_error_response
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
        ) from e


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    current_user: CurrentUser,
    session: DbSession,
    limit: int = 20,
    offset: int = 0,
) -> ChatHistoryResponse:
    """Get conversation history (paginated, newest first).

    Protected endpoint (requires valid JWT token).
    Returns messages in reverse chronological order (newest first).

    Args:
        limit: Max messages per page (default 20, max 100)
        offset: Pagination offset (default 0)
        current_user: Current authenticated user
        session: Database session

    Returns:
        ChatHistoryResponse with messages, total count, has_more flag
    """
    user_id = current_user.id

    try:
        # Validate pagination params
        limit = min(limit, 100)  # Cap at 100 to prevent abuse
        if limit < 1:
            limit = 20
        if offset < 0:
            offset = 0

        # Get user's conversation
        conversation = await ChatService.get_or_create_conversation(current_user.id, session)

        # Get total message count
        total = await ChatService.get_conversation_message_count(conversation.id, session)

        # Get paginated messages (newest first)
        messages = await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        # Convert to response format
        message_list = [
            ChatMessageResponse(
                id=str(msg.id),
                role=msg.role,
                content=msg.content,
                tokens_used=msg.tokens_used,
                created_at=msg.created_at.isoformat(),
            )
            for msg in messages.all()
        ]

        # Reverse to get chronological order for client
        message_list.reverse()

        # Calculate has_more
        has_more = (offset + limit) < total

        logger.info(
            f"Retrieved {len(message_list)} messages for user {user_id} "
            f"(total: {total}, offset: {offset})"
        )

        return ChatHistoryResponse(
            messages=message_list,
            total=total,
            has_more=has_more,
        )

    except Exception as e:
        logger.error(f"Failed to load chat history for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load chat history",
        ) from e
