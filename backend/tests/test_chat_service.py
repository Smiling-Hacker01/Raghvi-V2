"""Tests for ChatService business logic."""

import pytest

from app.models.message import Message
from app.models.user import User
from app.security.password import hash_password
from app.services.chat import ChatService

pytestmark = pytest.mark.asyncio


class TestChatService:
    """Tests for ChatService methods."""

    @pytest.fixture
    async def user(self, test_db):
        """Create a test user."""
        async with test_db() as session:
            user = User(
                username="servicetest",
                email="servicetest@example.com",
                password_hash=hash_password("TestPassword123"),
                name="Service Test",
                phone="9999999999",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    async def test_get_or_create_conversation_new(self, test_db, user):
        """Test creating a new conversation."""
        async with test_db() as session:
            conversation = await ChatService.get_or_create_conversation(user.id, session)

            assert conversation.user_id == user.id
            assert conversation.title == "Conversation"
            assert conversation.id is not None

    async def test_get_or_create_conversation_existing(self, test_db, user):
        """Test retrieving existing conversation."""
        async with test_db() as session:
            # Create first time
            conv1 = await ChatService.get_or_create_conversation(user.id, session)
            conv1_id = conv1.id

            # Get second time (should be same)
            conv2 = await ChatService.get_or_create_conversation(user.id, session)

            assert conv2.id == conv1_id

    async def test_get_recent_messages(self, test_db, user):
        """Test retrieving recent messages."""
        async with test_db() as session:
            # Create conversation with messages
            conversation = await ChatService.get_or_create_conversation(user.id, session)

            message1 = Message(
                conversation_id=conversation.id,
                role="user",
                content="First message",
            )
            message2 = Message(
                conversation_id=conversation.id,
                role="assistant",
                content="Response message",
            )
            session.add_all([message1, message2])
            await session.commit()

            # Get recent messages
            messages = await ChatService.get_recent_messages(
                conversation.id, limit=10, session=session
            )

            assert len(messages) == 2
            assert messages[0]["role"] == "user"
            assert messages[1]["role"] == "assistant"

    async def test_get_conversation_message_count(self, test_db, user):
        """Test getting message count."""
        async with test_db() as session:
            conversation = await ChatService.get_or_create_conversation(user.id, session)

            # Initially 0
            count1 = await ChatService.get_conversation_message_count(conversation.id, session)
            assert count1 == 0

            # Add messages
            for i in range(3):
                msg = Message(
                    conversation_id=conversation.id,
                    role="user",
                    content=f"Message {i}",
                )
                session.add(msg)
            await session.commit()

            # Check count again
            count2 = await ChatService.get_conversation_message_count(conversation.id, session)
            assert count2 == 3
