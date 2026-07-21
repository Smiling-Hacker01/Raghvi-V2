"""Chat service - business logic for chat operations."""

import logging
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services.ai.prompt import build_system_prompt
from app.services.ai.client import get_ai_client

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

        # Create new conversation
        conversation = Conversation(user_id=user_id, title="Conversation")
        session.add(conversation)
        await session.flush()  # Get the ID

        logger.info(f"Created new conversation for user {user_id}")
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
        user_id: UUID,
        user_message_content: str,
        session: AsyncSession,
    ) -> dict:
        """Send a message and get Raghvi response.

        Orchestrates:
        1. Load conversation + recent messages
        2. Load user profile + memories (Sprint 03+)
        3. Build system prompt
        4. Call LLM via AIClient
        5. Store both messages in DB
        6. Return response to user

        Args:
            user_id: User UUID
            user_message_content: User's message
            session: Database session

        Returns:
            Dict with user_message, assistant_message, tokens_used

        Raises:
            Exception: If all LLM providers fail
        """
        try:
            # 1. Get or create conversation
            conversation = await ChatService.get_or_create_conversation(user_id, session)

            # 2. Get recent messages for context (limit=8 for optimal latency)
            recent_messages = await ChatService.get_recent_messages(
                conversation.id, limit=10, session=session
            )

            # 3. Get user profile (name at minimum)
            user = await session.scalar(select(User).where(User.id == user_id))
            if not user:
                raise ValueError(f"User {user_id} not found")

            # 4. TODO: Load approved memories (Sprint 03)
            # For now, empty list
            user_memories = []

            # 5. Build system prompt (Raghvi personality)
            system_prompt = build_system_prompt(
                user_name=user.username,
                user_profile=f"Email: {user.email}",  # Minimal for now
                user_memories=user_memories,
            )

            # 6. Add user's new message to context
            context_messages = recent_messages + [{"role": "user", "content": user_message_content}]

            # 7. Call LLM (using singleton client for HTTP connection reuse)
            client = get_ai_client()
            response_text, tokens_used, provider_used = await client.send_message(
                messages=context_messages,
                system_prompt=system_prompt,
                max_tokens=1000,
                temperature=0.7,
            )

            # 8. Store user message
            user_message = Message(
                conversation_id=conversation.id,
                role="user",
                content=user_message_content,
                tokens_used=0,  # User messages don't use tokens
            )
            session.add(user_message)

            # 9. Store assistant message
            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=response_text,
                tokens_used=tokens_used,
            )
            session.add(assistant_message)

            # 10. Commit to database
            await session.commit()

            logger.info(
                f"Message stored for user {user_id} "
                f"via provider {provider_used} ({tokens_used} tokens)"
            )

            return {
                "user_message": user_message_content,
                "assistant_message": response_text,
                "tokens_used": tokens_used,
                # Note: provider_used is NOT returned to client
            }

        except Exception as e:
            logger.error(f"Chat error for user {user_id}: {e}")
            await session.rollback()
            raise
