import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from openai import APITimeoutError, RateLimitError, APIError, AuthenticationError, NotFoundError
from app.services.ai.providers.openai import OpenAIAdapter
from app.services.ai.providers.gemini import GeminiAdapter
from app.core.config import Settings

@pytest.fixture
def mock_openai_settings():
    return Settings(
        openai_api_key="sk-test-key",
        openai_model="gpt-4o",
        openai_timeout_seconds=30,
        ai_provider="openai"
    )

@pytest.fixture
def mock_gemini_settings():
    return Settings(
        gemini_api_key="AIzaSy-test-key",
        gemini_model="gemini-1.5-pro",
        gemini_timeout_seconds=30,
        ai_provider="gemini"
    )

class TestOpenAIAdapter:
    @patch("app.services.ai.providers.openai.get_settings")
    async def test_validate_config_success(self, mock_get_settings, mock_openai_settings):
        mock_get_settings.return_value = mock_openai_settings
        adapter = OpenAIAdapter()
        assert await adapter.validate_config() is True

    @patch("app.services.ai.providers.openai.get_settings")
    @patch("app.services.ai.providers.openai.AsyncOpenAI")
    async def test_validate_config_missing_key(self, mock_async_openai, mock_get_settings, mock_openai_settings):
        mock_openai_settings.openai_api_key = None
        mock_get_settings.return_value = mock_openai_settings
        adapter = OpenAIAdapter()
        with pytest.raises(ValueError, match="OPENAI_API_KEY environment variable not set"):
            await adapter.validate_config()

    @patch("app.services.ai.providers.openai.get_settings")
    async def test_get_model_info(self, mock_get_settings, mock_openai_settings):
        mock_get_settings.return_value = mock_openai_settings
        adapter = OpenAIAdapter()
        info = adapter.get_model_info()
        assert info["provider"] == "openai"
        assert info["model_name"] == "gpt-4o"

    @patch("app.services.ai.providers.openai.get_settings")
    async def test_send_message_success(self, mock_get_settings, mock_openai_settings):
        mock_get_settings.return_value = mock_openai_settings
        
        with patch("app.services.ai.providers.openai.AsyncOpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Hello from OpenAI"
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            adapter = OpenAIAdapter()
            response, tokens = await adapter.send_message(
                messages=[{"role": "user", "content": "hi"}],
                system_prompt="system",
            )
            
            assert response == "Hello from OpenAI"
            assert tokens > 0

    @patch("app.services.ai.providers.openai.get_settings")
    async def test_send_message_rate_limit(self, mock_get_settings, mock_openai_settings):
        mock_get_settings.return_value = mock_openai_settings
        
        with patch("app.services.ai.providers.openai.AsyncOpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            
            mock_response = MagicMock()
            mock_client.chat.completions.create = AsyncMock(side_effect=RateLimitError("Rate limit", response=mock_response, body=None))
            
            adapter = OpenAIAdapter()
            with pytest.raises(RateLimitError):
                await adapter.send_message([], "system")

class TestGeminiAdapter:
    @patch("app.services.ai.providers.gemini.get_settings")
    async def test_validate_config_success(self, mock_get_settings, mock_gemini_settings):
        mock_get_settings.return_value = mock_gemini_settings
        with patch("app.services.ai.providers.gemini.Client"):
            adapter = GeminiAdapter()
            assert await adapter.validate_config() is True

    @patch("app.services.ai.providers.gemini.get_settings")
    async def test_send_message_success(self, mock_get_settings, mock_gemini_settings):
        mock_get_settings.return_value = mock_gemini_settings
        
        with patch("app.services.ai.providers.gemini.Client"):
            adapter = GeminiAdapter()
            
            with patch.object(adapter, '_call_gemini', return_value="Hello from Gemini"):
                response, tokens = await adapter.send_message(
                    messages=[{"role": "user", "content": "hi"}],
                    system_prompt="system",
                )
                
                assert response == "Hello from Gemini"
                assert tokens > 0
