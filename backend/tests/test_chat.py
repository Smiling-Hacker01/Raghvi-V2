"""Tests for chat endpoints."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestChatSend:
    """Tests for POST /chat/send endpoint."""

    async def test_send_message_success(self, client: AsyncClient, auth_headers: dict):
        """Test successful message sending."""
        response = await client.post(
            "/chat/send",
            json={"content": "Hi Raghvi, how are you?"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "user_message" in data
        assert "assistant_message" in data
        assert "tokens_used" in data

        # Verify content
        assert data["user_message"] == "Hi Raghvi, how are you?"
        assert len(data["assistant_message"]) > 0
        assert data["tokens_used"] >= 0

        # Verify no provider exposed
        assert "provider" not in data

    async def test_send_message_without_auth(self, client: AsyncClient):
        """Test message sending without authentication."""
        response = await client.post(
            "/chat/send",
            json={"content": "Hello"},
        )

        assert response.status_code == 401

    async def test_send_empty_message(self, client: AsyncClient, auth_headers: dict):
        """Test sending empty message (validation error)."""
        response = await client.post(
            "/chat/send",
            json={"content": ""},
            headers=auth_headers,
        )

        assert response.status_code == 422

    async def test_send_message_too_long(self, client: AsyncClient, auth_headers: dict):
        """Test sending message exceeding max length."""
        long_message = "x" * 6000  # Exceeds 5000 char limit
        response = await client.post(
            "/chat/send",
            json={"content": long_message},
            headers=auth_headers,
        )

        assert response.status_code == 422

    async def test_send_message_stores_in_db(
        self, client: AsyncClient, auth_headers: dict, test_db
    ):
        """Test that message is stored in database."""
        # Send message
        response = await client.post(
            "/chat/send",
            json={"content": "Test message"},
            headers=auth_headers,
        )

        assert response.status_code == 200

        # Verify in database
        from sqlalchemy import select

        from app.models.message import Message

        async with test_db() as session:
            messages = await session.scalars(select(Message))
            message_list = messages.all()

            # Should have at least 2 messages (user + assistant)
            assert len(message_list) >= 2

            # Verify user message
            user_msg = [m for m in message_list if m.role == "user"][0]
            assert user_msg.content == "Test message"

            # Verify assistant message exists
            assistant_msgs = [m for m in message_list if m.role == "assistant"]
            assert len(assistant_msgs) > 0
            assert len(assistant_msgs[0].content) > 0


class TestChatHistory:
    """Tests for GET /chat/history endpoint."""

    async def test_get_empty_history(self, client: AsyncClient, auth_headers: dict):
        """Test getting history when no messages exist."""
        response = await client.get(
            "/chat/history",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 0
        assert len(data["messages"]) == 0
        assert data["has_more"] is False

    async def test_get_history_after_sending_message(self, client: AsyncClient, auth_headers: dict):
        """Test getting history after sending messages."""
        # Send a message first
        await client.post(
            "/chat/send",
            json={"content": "Hello Raghvi"},
            headers=auth_headers,
        )

        # Get history
        response = await client.get(
            "/chat/history",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should have at least 2 messages (user + assistant)
        assert data["total"] >= 2
        assert len(data["messages"]) >= 2

        # Verify message order (chronological)
        messages = data["messages"]
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello Raghvi"
        assert messages[1]["role"] == "assistant"

    async def test_history_pagination(self, client: AsyncClient, auth_headers: dict):
        """Test pagination with limit and offset."""
        # Send multiple messages
        for i in range(5):
            await client.post(
                "/chat/send",
                json={"content": f"Message {i}"},
                headers=auth_headers,
            )

        # Get first page (limit=2)
        response1 = await client.get(
            "/chat/history?limit=2&offset=0",
            headers=auth_headers,
        )

        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1["messages"]) <= 2
        assert data1["has_more"] is True  # More messages exist

        # Get second page
        response2 = await client.get(
            "/chat/history?limit=2&offset=2",
            headers=auth_headers,
        )

        assert response2.status_code == 200
        data2 = response2.json()

        # Pages should be different
        assert data1["messages"][0]["id"] != data2["messages"][0]["id"]

    async def test_history_without_auth(self, client: AsyncClient):
        """Test getting history without authentication."""
        response = await client.get("/chat/history")

        assert response.status_code == 401

    async def test_history_max_limit(self, client: AsyncClient, auth_headers: dict):
        """Test that limit is capped at 100."""
        response = await client.get(
            "/chat/history?limit=500",
            headers=auth_headers,
        )

        assert response.status_code == 200
        # Should not error, just cap the limit


class TestConversation:
    """Tests for GET /chat/ endpoint."""

    async def test_get_conversation_creates_if_not_exists(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test that conversation is created on first access."""
        response = await client.get(
            "/chat/",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "id" in data
        assert "user_id" in data
        assert "title" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert "message_count" in data

        # First access should have 0 messages
        assert data["message_count"] == 0

    async def test_get_conversation_returns_same(self, client: AsyncClient, auth_headers: dict):
        """Test that same conversation is returned on multiple calls."""
        response1 = await client.get("/chat/", headers=auth_headers)
        conv_id_1 = response1.json()["id"]

        response2 = await client.get("/chat/", headers=auth_headers)
        conv_id_2 = response2.json()["id"]

        # Should be the same conversation
        assert conv_id_1 == conv_id_2

    async def test_conversation_message_count_updates(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test that message count updates after sending messages."""
        # Initial count
        response1 = await client.get("/chat/", headers=auth_headers)
        count1 = response1.json()["message_count"]
        assert count1 == 0

        # Send a message
        await client.post(
            "/chat/send",
            json={"content": "Test"},
            headers=auth_headers,
        )

        # Check count again
        response2 = await client.get("/chat/", headers=auth_headers)
        count2 = response2.json()["message_count"]

        # Should have increased (at least 2: user + assistant)
        assert count2 > count1
