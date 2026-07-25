import asyncio
import logging
from typing import Any

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.services.ai.adapter import AIProviderAdapter

logger = logging.getLogger(__name__)


class OpenRouterAdapter(AIProviderAdapter):
    """OpenRouter provider adapter.

    Implements AIProviderAdapter for OpenRouter's unified LLM API.
    OpenRouter uses OpenAI-compatible API format.
    """

    def __init__(self):
        settings = get_settings()

        self.api_key = settings.open_router_api_key
        self.model = settings.open_router_model
        self.timeout = settings.open_router_timeout_seconds
        self.max_retries = 3
        self.retry_delay = 1

        # OpenRouter uses OpenAI-compatible API at api.openrouter.ai
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1",
            timeout=self.timeout,
        )

    async def validate_config(self) -> bool:
        """Validate OpenRouter configuration."""
        if not self.api_key:
            raise ValueError("OPEN_ROUTER_API_KEY environment variable not set")

        if not self.api_key.startswith("sk-or-v1-"):
            raise ValueError(
                "OPEN_ROUTER_API_KEY format is invalid (should start with 'sk-or-v1-')"
            )

        return True

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the configured OpenRouter model."""
        return {
            "model_name": self.model,
            "provider": "openrouter",
            "max_tokens": 8192,
            "timeout_seconds": self.timeout,
        }

    def _count_tokens(self, text: str) -> int:
        """Estimate token count."""
        return len(text) // 4

    async def send_message(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> tuple[str, int]:
        """Send messages to OpenRouter and get response.

        Args:
            messages: Conversation history
            system_prompt: System prompt for personality/context
            max_tokens: Max tokens in response
            temperature: Sampling temperature

        Returns:
            Tuple of (response_text, tokens_used)

        Raises:
            Exception: If LLM call fails
        """
        full_messages = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        last_error = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"OpenRouter API call (attempt {attempt + 1}/{self.max_retries})")

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=full_messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                response_text = response.choices[0].message.content or ""

                # Use actual token counts from API response
                prompt_tokens = getattr(response.usage, "prompt_tokens", 0)
                completion_tokens = getattr(response.usage, "completion_tokens", 0)
                tokens_used = prompt_tokens + completion_tokens

                logger.debug(
                    f"OpenRouter response received: {len(response_text)} chars, "
                    f"{tokens_used} tokens"
                )
                return response_text, tokens_used

            except Exception as e:
                last_error = e
                err_str = str(e)

                # Check for rate limit errors
                is_rate_limit = "429" in err_str or "rate_limit" in err_str.lower()
                if is_rate_limit:
                    logger.error(f"OpenRouter rate limit error (no retry): {e}")
                    raise

                logger.warning(
                    f"OpenRouter API error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2**attempt)
                    await asyncio.sleep(wait_time)

        logger.error(f"OpenRouter API failed after {self.max_retries} attempts: {last_error}")
        raise last_error or Exception("OpenRouter API call failed")
