"""Chat service - business logic for chat operations."""

import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services.ai.client import get_ai_client
from app.services.ai.prompt import build_system_prompt, get_error_response
from app.services.memory.extractor import MemoryExtractor
from app.services.memory.retrieval import get_retriever

logger = logging.getLogger(__name__)


class ChatService:
    """Service for chat operations."""

    @staticmethod
    async def get_or_create_conversation(user_id: UUID, session: AsyncSession) -> Conversation:
        """Get user's conversation or create new one (one per user).

        Args:
            user_id: User UUID
            session: Database session

        Returns:
            Conversation object
        """
        # Get existing conversation
        conversation = await session.scalar(
            select(Conversation).where(Conversation.user_id == user_id)
        )

        if conversation:
            return conversation

        # Try to create new conversation
        conversation = Conversation(user_id=user_id, title="Conversation")
        session.add(conversation)

        try:
            await session.commit()  # Persist so subsequent requests see the same conversation
            await session.refresh(conversation)
            logger.info(f"Created new conversation for user {user_id}")
            return conversation
        except IntegrityError:
            # Another request created it simultaneously — fetch it
            await session.rollback()
            conversation = await session.scalar(
                select(Conversation).where(Conversation.user_id == user_id)
            )
            logger.info(f"Conversation already exists for user {user_id}")
            return conversation

    @staticmethod
    async def get_recent_messages(
        conversation_id: UUID, limit: int = 20, session: AsyncSession = None
    ) -> list[dict[str, str]]:
        """Get recent messages from conversation (for LLM context).

        Args:
            conversation_id: Conversation UUID
            limit: Max messages to retrieve
            session: Database session (if None, creates new connection)

        Returns:
            List of message dicts {"role": "user"/"assistant", "content": "..."}
        """
        if session is None:
            async with AsyncSession(engine) as session:
                return await ChatService.get_recent_messages(conversation_id, limit, session)

        messages = await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )

        # Reverse to get chronological order
        return [{"role": msg.role, "content": msg.content} for msg in reversed(messages.all())]

    @staticmethod
    async def get_conversation_message_count(conversation_id: UUID, session: AsyncSession) -> int:
        """Get total message count in conversation."""
        count = await session.scalar(
            select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
        )
        return count or 0

    @staticmethod
    async def send_message(
        user_id: str,
        user_message_content: str,
        session: AsyncSession,
    ) -> dict:
        """Send a message and get AI response with memory context.
    
        Flow:
        1. Get or create conversation
        2. Retrieve relevant memories
        3. Build system prompt with memory context
        4. Call LLM
        5. Store messages
    
        Args:
            user_id: User's UUID
            user_message_content: Message content from user
            session: Database session
        
        Returns:
            Dict with user_message, assistant_message, tokens_used
        
        Raises:
            ValueError: If content invalid
        """
        # Validate
        if not user_message_content or not user_message_content.strip():
            raise ValueError("Message cannot be empty")

        if len(user_message_content) > 5000:
            raise ValueError("Message exceeds maximum length")

        # Get or create conversation
        conversation = await ChatService.get_or_create_conversation(user_id, session)

        # Retrieve relevant memories for context
        retriever = get_retriever(top_k=9)
        relevant_memories = await retriever.retrieve(
            user_id=user_id,
            query=user_message_content,
            session=session,
        )

        logger.info(
            f"Chat for user {user_id}: "
            f"retrieved {len(relevant_memories)} relevant memories"
        )

        # Build system prompt with memory context
        system_prompt = build_system_prompt(relevant_memories)

        # Get recent message history for context window
        recent_messages = await ChatService.get_recent_messages(
            conversation.id,
            limit=15,
            session=session,
        )

        # Build messages list for LLM
        messages = []

        # Add recent conversation history
        for msg in recent_messages:
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message_content,
        })

        # Call LLM with context
        try:
            client = get_ai_client()
            response_text, tokens_used, provider_used = await client.send_message(
                messages=messages,
                system_prompt=system_prompt,
            )

            logger.info(
                f"LLM response for user {user_id}: "
                f"provider={provider_used}, tokens={tokens_used}"
            )

        except Exception as e:
            logger.error(f"LLM error for user {user_id}: {e}")
            response_text = get_error_response()
            tokens_used = 0
    
        # Store user message
        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=user_message_content,
            tokens_used=None,
        )
        session.add(user_msg)
    
        # Store assistant message
        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=response_text,
            tokens_used=tokens_used,
        )
        session.add(assistant_msg)

        # Auto-extract personal facts into user memory bank
        try:
            await MemoryExtractor.extract_and_save_memories(
                user_id=user_id,
                message=user_message_content,
                session=session,
            )
        except Exception as e:
            logger.warning(f"Auto memory extraction failed for user {user_id}: {e}")

        await session.commit()
    
        logger.info(
            f"Messages stored for conversation {conversation.id}: "
            f"user_msg={user_msg.id}, assistant_msg={assistant_msg.id}"
        )
    
        return {
            "user_message": user_message_content,
            "assistant_message": response_text,
        "tokens_used": tokens_used,
    }