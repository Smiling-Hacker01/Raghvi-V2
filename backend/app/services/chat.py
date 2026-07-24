"""Chat service - business logic for chat operations."""

import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine
from app.models.conversation import Conversation
from app.models.message import Message
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
        skip_background_extraction: bool = False,
    ) -> dict:
        """Send a message and get AI response with memory context.

        Flow (Optimized):
        1. Get or create conversation + retrieve memories in parallel
        2. Build system prompt with memory context (cached creator profile)
        3. Call LLM
        4. Store messages and extract memories in parallel
        5. Return response immediately (memory extraction happens async)

        Args:
            user_id: User's UUID
            user_message_content: Message content from user
            session: Database session
            skip_background_extraction: If True, don't extract memories (for testing)

        Returns:
            Dict with user_message, assistant_message, tokens_used

        Raises:
            ValueError: If content invalid
        """
        import asyncio

        # Validate
        if not user_message_content or not user_message_content.strip():
            raise ValueError("Message cannot be empty")

        if len(user_message_content) > 5000:
            raise ValueError("Message exceeds maximum length")

        # OPTIMIZATION 1: Parallelize conversation + memory retrieval
        conversation_task = ChatService.get_or_create_conversation(user_id, session)

        retriever = get_retriever(top_k=9)
        memories_task = retriever.retrieve(
            user_id=user_id,
            query=user_message_content,
            session=session,
        )

        # Wait for both in parallel
        conversation, relevant_memories = await asyncio.gather(
            conversation_task,
            memories_task,
        )

        logger.info(
            f"Chat for user {user_id}: retrieved {len(relevant_memories)} relevant memories"
        )

        # OPTIMIZATION 2: Build system prompt (with cached creator profile)
        system_prompt = await build_system_prompt(relevant_memories, session)

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
            messages.append(
                {
                    "role": msg["role"],
                    "content": msg["content"],
                }
            )

        # Add current user message
        messages.append(
            {
                "role": "user",
                "content": user_message_content,
            }
        )

        # Call LLM with context
        try:
            client = get_ai_client()
            response_text, tokens_used, provider_used = await client.send_message(
                messages=messages,
                system_prompt=system_prompt,
            )

            logger.info(
                f"LLM response for user {user_id}: provider={provider_used}, tokens={tokens_used}"
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

        # OPTIMIZATION 3: Commit messages first to return response faster
        await session.commit()

        logger.info(
            f"Messages stored for conversation {conversation.id}: "
            f"user_msg={user_msg.id}, assistant_msg={assistant_msg.id}"
        )

        # OPTIMIZATION 4: Extract memories (async in production, sync in tests)
        if not skip_background_extraction:
            # In production: background task (non-blocking)
            asyncio.create_task(
                ChatService._extract_memories_background(
                    user_id=user_id,
                    message=user_message_content,
                )
            )
        else:
            # In tests: synchronous extraction
            try:
                await MemoryExtractor.extract_and_save_memories(
                    user_id=user_id,
                    message=user_message_content,
                    session=session,
                )
                await session.commit()
            except Exception as e:
                logger.warning(f"Memory extraction failed for user {user_id}: {e}")

        return {
            "user_message": user_message_content,
            "assistant_message": response_text,
            "tokens_used": tokens_used,
        }

    @staticmethod
    async def _extract_memories_background(user_id: str, message: str) -> None:
        """Extract memories in background (non-blocking).

        This runs asynchronously after the response is sent to user.

        Args:
            user_id: User's UUID
            message: User message content
        """
        try:
            # Create new session for background task
            from app.db.session import async_session_maker

            async with async_session_maker() as session:
                await MemoryExtractor.extract_and_save_memories(
                    user_id=user_id,
                    message=message,
                    session=session,
                )
                await session.commit()
        except Exception as e:
            logger.warning(f"Background memory extraction failed for user {user_id}: {e}")
