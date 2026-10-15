"""Chat service - business logic for chat operations."""

import asyncio
import logging
import re
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

        # Validate
        if not user_message_content or not user_message_content.strip():
            raise ValueError("Message cannot be empty")

        if len(user_message_content) > 5000:
            raise ValueError("Message exceeds maximum length")

        # Web research classification (external network/mock)
        from app.services.research import ResearchRequest, get_research_service
        from app.services.task_service import TaskService

        research_service = get_research_service()
        needs_search, search_query = research_service.classify_query(user_message_content)

        research_task = None
        if needs_search:
            research_task = asyncio.create_task(
                research_service.execute_research(
                    ResearchRequest(query=search_query, max_results=4)
                )
            )

        # Database session queries executed sequentially to maintain session safety
        conversation = await ChatService.get_or_create_conversation(user_id, session)

        retriever = get_retriever(top_k=9)
        relevant_memories = await retriever.retrieve(
            user_id=user_id,
            query=user_message_content,
            session=session,
        )

        active_tasks = await TaskService.get_active_tasks(
            user_id=str(user_id),
            session=session,
        )

        research_resp = await research_task if research_task else None

        logger.info(
            f"Chat for user {user_id}: retrieved {len(relevant_memories)} memories, "
            f"{len(active_tasks)} active tasks, "
            f"research={bool(research_resp and research_resp.performed_search)}"
        )

        # Autonomous Communication Context (Email, WhatsApp, Meetings)
        from app.services.communication_service import CommunicationService

        comm_intent = CommunicationService.parse_communication_intent(user_message_content)
        comm_context_str = None

        if comm_intent:
            try:
                intent_type = comm_intent.get("type")
                if intent_type == "check_email":
                    acc_label = comm_intent.get("account_label")
                    emails = await CommunicationService.get_emails(
                        user_id=str(user_id),
                        sender_query=comm_intent.get("sender"),
                        account_label_query=acc_label,
                        unread_only=comm_intent.get("unread_only", False),
                        session=session,
                    )
                    if emails:
                        items = [
                            f"- [{e.account_label or 'Mail'}] {e.sender_name}\n  {e.body[:60]}"
                            for e in emails[:4]
                        ]
                        comm_context_str = (
                            f"[COMMUNICATION STATUS: EMAILS FOUND]\n"
                            f"Found {len(emails)} emails (target account: {acc_label or 'all'}):\n"
                            + "\n".join(items)
                        )
                    else:
                        target_str = f" in {acc_label} account" if acc_label else ""
                        comm_context_str = (
                            f"[COMMUNICATION STATUS: No new/matching emails found{target_str}]"
                        )

                elif intent_type == "reply_email":
                    acc_label = comm_intent.get("account_label")
                    emails = await CommunicationService.get_emails(
                        user_id=str(user_id),
                        account_label_query=acc_label,
                        limit=1,
                        session=session,
                    )
                    if emails:
                        target = emails[0]
                        thread = await CommunicationService.get_email_thread(
                            user_id=str(user_id),
                            email_id=target.id,
                            session=session,
                        )
                        draft = CommunicationService.draft_human_email_reply(
                            target_email=target,
                            thread=thread,
                            user_instructions=comm_intent.get("query"),
                        )
                        comm_context_str = (
                            f"[COMMUNICATION STATUS: EMAIL REPLY DRAFTED]\n"
                            f"Account: {target.account_label or 'Default'} ({target.recipient})\n"
                            f"Email from: {target.sender_name} <{target.sender}>\n"
                            f"Subject: {target.subject}\n"
                            f"Original content: {target.body}\n"
                            f"Prepared completely human reply:\n{draft}\n"
                            f"Action: Tell user what was asked and what you are replying."
                        )
                    else:
                        comm_context_str = "[COMMUNICATION STATUS: No email found to reply to]"

                elif intent_type == "check_whatsapp":
                    sender = comm_intent.get("sender")
                    acc_label = comm_intent.get("account_label")
                    msgs = await CommunicationService.get_whatsapp_messages(
                        user_id=str(user_id),
                        sender_name=sender,
                        account_label_query=acc_label,
                        session=session,
                    )
                    if msgs:
                        m_list = [
                            f"- [{m.account_label or 'WhatsApp'}] {m.sender_name}: '{m.body}'"
                            for m in msgs[:4]
                        ]
                        target_acc = acc_label or "all accounts"
                        comm_context_str = (
                            f"[COMMUNICATION STATUS: WHATSAPP MESSAGES FOUND]\n"
                            f"Messages from {sender or 'contacts'} ({target_acc}):\n"
                            + "\n".join(m_list)
                        )
                    else:
                        contact_label = sender or "contacts"
                        comm_context_str = (
                            f"[COMMUNICATION STATUS: No new messages from {contact_label}]"
                        )

                elif intent_type == "reply_whatsapp":
                    sender = comm_intent.get("sender")
                    acc_label = comm_intent.get("account_label")
                    msgs = await CommunicationService.get_whatsapp_messages(
                        user_id=str(user_id),
                        sender_name=sender,
                        account_label_query=acc_label,
                        session=session,
                    )
                    if msgs:
                        draft = CommunicationService.draft_human_whatsapp_reply(
                            recent_messages=msgs,
                            user_instructions=comm_intent.get("instructions"),
                        )
                        target = msgs[0]
                        comm_context_str = (
                            f"[COMMUNICATION STATUS: WHATSAPP REPLY DRAFTED]\n"
                            f"Account: {target.account_label or 'WhatsApp'}\n"
                            f"Contact: {target.sender_name}\n"
                            f"Their message: {target.body}\n"
                            f"Prepared human reply: '{draft}'\n"
                            f"Action: Tell user what was received and what reply is prepared."
                        )
                    else:
                        contact_name = sender or "contact"
                        comm_context_str = (
                            f"[COMMUNICATION STATUS: No messages from {contact_name} to reply to]"
                        )

                elif intent_type == "schedule_meeting":
                    proposal = await CommunicationService.schedule_meeting_action(
                        user_id=str(user_id),
                        title=comm_intent.get("title", "Meeting"),
                        date=comm_intent.get("date", "today"),
                        start_time=comm_intent.get("time", "3:00 PM"),
                        attendees=comm_intent.get("attendees", []),
                        session=session,
                    )
                    comm_context_str = (
                        f"[COMMUNICATION STATUS: MEETING SCHEDULED]\n"
                        f"Created proposal: {proposal.description}.\n"
                        f"Action: Warmly confirm meeting and attendee invites are prepared."
                    )
            except Exception as e:
                logger.warning(f"Communication processing error: {e}")

        # OPTIMIZATION 2: Build system prompt (with memories, tasks, research & comms)
        system_prompt = await build_system_prompt(
            user_memories=relevant_memories,
            session=session,
            user_tasks=active_tasks,
            web_research_context=research_resp.synthesized_context if research_resp else None,
            communication_context=comm_context_str,
        )

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
            raw_response_text, tokens_used, provider_used = await client.send_message(
                messages=messages,
                system_prompt=system_prompt,
            )

            logger.info(
                f"LLM response for user {user_id}: provider={provider_used}, tokens={tokens_used}"
            )

            # Parse XML-like structure for emotion, voice, and chat
            emotion = "neutral"
            voice_text = raw_response_text
            chat_text = raw_response_text

            _flags = re.DOTALL | re.IGNORECASE
            emotion_match = re.search(r"<emotion>(.*?)</emotion>", raw_response_text, _flags)
            voice_match = re.search(r"<voice_text>(.*?)</voice_text>", raw_response_text, _flags)
            chat_match = re.search(r"<chat_text>(.*?)</chat_text>", raw_response_text, _flags)

            if emotion_match:
                emotion = emotion_match.group(1).strip().lower()
            if voice_match:
                voice_text = voice_match.group(1).strip()
            if chat_match:
                chat_text = chat_match.group(1).strip()

        except Exception as e:
            logger.error(f"LLM error for user {user_id}: {e}")
            chat_text = get_error_response()
            voice_text = chat_text
            emotion = "sad"
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
            content=chat_text,
            tokens_used=tokens_used,
        )
        session.add(assistant_msg)

        # OPTIMIZATION 3: Commit messages first to return response faster
        await session.commit()

        logger.info(
            f"Messages stored for conversation {conversation.id}: "
            f"user_msg={user_msg.id}, assistant_msg={assistant_msg.id}"
        )

        # OPTIMIZATION 4: Extract memories and tasks (async in production, sync in tests)
        from app.services.task_extractor import TaskExtractor

        if not skip_background_extraction:
            # In production: background task (non-blocking)
            asyncio.create_task(
                ChatService._extract_memories_background(
                    user_id=user_id,
                    message=user_message_content,
                )
            )
            asyncio.create_task(
                ChatService._extract_tasks_background(
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

            try:
                extracted = await TaskExtractor.extract_tasks(
                    user_message=user_message_content,
                    session=session,
                )
                if extracted:
                    await TaskExtractor.create_tasks_from_extraction(
                        user_id=str(user_id),
                        extracted_tasks=extracted,
                        session=session,
                    )
            except Exception as e:
                logger.warning(f"Task extraction failed for user {user_id}: {e}")

        citations_data = [
            {
                "id": c.id,
                "title": c.title,
                "url": c.url,
                "snippet": c.snippet,
            }
            for c in (research_resp.citations if research_resp else [])
        ]

        return {
            "user_message": user_message_content,
            "assistant_message": chat_text,
            "voice_text": voice_text,
            "emotion": emotion,
            "tokens_used": tokens_used,
            "citations": citations_data,
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

    @staticmethod
    async def _extract_tasks_background(user_id: str, message: str) -> None:
        """Extract tasks in background (non-blocking).

        This runs asynchronously after the response is sent to user.

        Args:
            user_id: User's UUID
            message: User message content
        """
        try:
            from app.db.session import async_session_maker
            from app.services.task_extractor import TaskExtractor

            async with async_session_maker() as session:
                extracted = await TaskExtractor.extract_tasks(
                    user_message=message,
                    session=session,
                )
                if extracted:
                    await TaskExtractor.create_tasks_from_extraction(
                        user_id=str(user_id),
                        extracted_tasks=extracted,
                        session=session,
                    )
        except Exception as e:
            logger.warning(f"Background task extraction failed for user {user_id}: {e}")
