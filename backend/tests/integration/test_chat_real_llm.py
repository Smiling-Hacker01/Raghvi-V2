"""Integration tests using real LLM API (run only in CI with secrets)."""

import os

import pytest
from httpx import AsyncClient

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("RUN_LLM_INTEGRATION_TESTS"),
        reason="Set RUN_LLM_INTEGRATION_TESTS=1 to run"
    ),
]


class TestChatRealLLM:
    """Tests with real LLM providers (not mocked)."""

    async def test_chat_send_with_real_openai(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test /chat/send with real OpenAI API."""
        response = await client.post(
            "/chat/send",
            json={"content": "What is 2+2?"},
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response is sensible (not mocked)
        assert "assistant_message" in data
        assert len(data["assistant_message"]) > 10
        assert "4" in data["assistant_message"]  # 2+2=4

    async def test_chat_send_with_real_gemini(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test /chat/send with real Gemini API."""
        # This will use Gemini if OpenAI fails (failover test)
        response = await client.post(
            "/chat/send",
            json={"content": "Say hello!"},
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["assistant_message"]) > 0
