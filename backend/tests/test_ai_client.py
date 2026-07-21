import pytest
from unittest.mock import AsyncMock, patch

from app.services.ai.client import AIClient, get_ai_client
from app.services.ai.errors import AIConfigurationError, AIProviderFailureError

class TestAIClient:
    @patch("app.services.ai.client.AIProviderChain")
    async def test_send_message_success(self, mock_chain_cls):
        mock_chain = mock_chain_cls.return_value
        mock_chain.provider_chain = [("mock", None)]
        mock_chain.send_message = AsyncMock(return_value=("Client Response", 20, "mock"))
        
        client = AIClient()
        response, tokens, provider = await client.send_message([], "sys")
        
        assert response == "Client Response"
        assert provider == "mock"
        
    @patch("app.services.ai.client.AIProviderChain")
    async def test_send_message_all_fail(self, mock_chain_cls):
        mock_chain = mock_chain_cls.return_value
        mock_chain.provider_chain = [("mock", None)]
        mock_chain.send_message = AsyncMock(side_effect=RuntimeError("Fail"))
        
        client = AIClient()
        with pytest.raises(AIProviderFailureError, match="My mind just went blank"):
            await client.send_message([], "sys")

    @patch("app.services.ai.client.AIProviderChain")
    def test_get_available_providers(self, mock_chain_cls):
        mock_chain = mock_chain_cls.return_value
        mock_chain.get_available_providers.return_value = ["openai", "gemini"]
        
        client = AIClient()
        assert client.get_available_providers() == ["openai", "gemini"]

def test_get_ai_client_singleton():
    with patch("app.services.ai.client.AIClient") as mock_cls:
        mock_cls.return_value = "fake_client"
        client1 = get_ai_client()
        client2 = get_ai_client()
        
        assert client1 == client2
        mock_cls.assert_called_once()
