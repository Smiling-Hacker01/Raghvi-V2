from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.services.ai.chain import AIProviderChain


@pytest.fixture
def chain_settings():
    return Settings(
        ai_provider="openai",
        openai_api_key="sk-chain-test",
        gemini_api_key="AIzaSy-chain-test",
    )


class TestAIProviderChain:
    @patch("app.services.ai.chain.get_settings")
    @patch("app.services.ai.providers.openai.OpenAIAdapter")
    @patch("app.services.ai.providers.gemini.GeminiAdapter")
    def test_build_chain_all_available(
        self, mock_gemini_cls, mock_openai_cls, mock_get_settings, chain_settings
    ):
        mock_get_settings.return_value = chain_settings

        chain = AIProviderChain()

        assert len(chain.provider_chain) == 2
        assert chain.provider_chain[0][0] == "openai"
        assert chain.provider_chain[1][0] == "gemini"

    @patch("app.services.ai.chain.get_settings")
    @patch("app.services.ai.providers.openai.OpenAIAdapter")
    def test_build_chain_only_openai(self, mock_openai_cls, mock_get_settings, chain_settings):
        chain_settings.gemini_api_key = None
        mock_get_settings.return_value = chain_settings

        chain = AIProviderChain()

        assert len(chain.provider_chain) == 1
        assert chain.provider_chain[0][0] == "openai"

    @patch("app.services.ai.chain.get_settings")
    @patch("app.services.ai.providers.openai.OpenAIAdapter")
    @patch("app.services.ai.providers.gemini.GeminiAdapter")
    async def test_send_message_success_primary(
        self, mock_gemini_cls, mock_openai_cls, mock_get_settings, chain_settings
    ):
        mock_get_settings.return_value = chain_settings

        # Setup mocks
        mock_openai_adapter = mock_openai_cls.return_value
        mock_openai_adapter.send_message = AsyncMock(return_value=("OpenAI Response", 10))

        mock_gemini_adapter = mock_gemini_cls.return_value
        mock_gemini_adapter.send_message = AsyncMock()

        chain = AIProviderChain()
        response, tokens, provider = await chain.send_message([], "sys")

        assert response == "OpenAI Response"
        assert provider == "openai"
        mock_openai_adapter.send_message.assert_called_once()
        mock_gemini_adapter.send_message.assert_not_called()

    @patch("app.services.ai.chain.get_settings")
    @patch("app.services.ai.providers.openai.OpenAIAdapter")
    @patch("app.services.ai.providers.gemini.GeminiAdapter")
    async def test_send_message_failover(
        self, mock_gemini_cls, mock_openai_cls, mock_get_settings, chain_settings
    ):
        mock_get_settings.return_value = chain_settings

        mock_openai_adapter = mock_openai_cls.return_value
        # OpenAI fails
        mock_openai_adapter.send_message = AsyncMock(side_effect=Exception("OpenAI down"))

        mock_gemini_adapter = mock_gemini_cls.return_value
        # Gemini succeeds
        mock_gemini_adapter.send_message = AsyncMock(return_value=("Gemini Response", 15))

        chain = AIProviderChain()
        response, tokens, provider = await chain.send_message([], "sys")

        assert response == "Gemini Response"
        assert provider == "gemini"
        mock_openai_adapter.send_message.assert_called_once()
        mock_gemini_adapter.send_message.assert_called_once()

    @patch("app.services.ai.chain.get_settings")
    @patch("app.services.ai.providers.openai.OpenAIAdapter")
    @patch("app.services.ai.providers.gemini.GeminiAdapter")
    async def test_send_message_all_fail(
        self, mock_gemini_cls, mock_openai_cls, mock_get_settings, chain_settings
    ):
        mock_get_settings.return_value = chain_settings

        mock_openai_adapter = mock_openai_cls.return_value
        mock_openai_adapter.send_message = AsyncMock(side_effect=Exception("OpenAI down"))

        mock_gemini_adapter = mock_gemini_cls.return_value
        mock_gemini_adapter.send_message = AsyncMock(side_effect=Exception("Gemini down"))

        chain = AIProviderChain()
        with pytest.raises(RuntimeError, match="All AI providers failed"):
            await chain.send_message([], "sys")
