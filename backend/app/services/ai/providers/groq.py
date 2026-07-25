import asyncio
import logging
from typing import Any

from groq import AsyncGroq

from app.core.config import get_settings
from app.services.ai.adapter import AIProviderAdapter

logger = logging.getLogger(__name__)


class GroqAdapter(AIProviderAdapter):
    """Groq provider adapter.

    Implements AIProviderAdapter for Groq's fast inference API.
    """

    def __init__(self):
        settings = get_settings()

        self.api_key = settings.groq_api_key
        self.model = settings.groq_model
        self.timeout = settings.groq_timeout_seconds
        self.max_retries = 3
        self.retry_delay = 1

        self.client = AsyncGroq(api_key=self.api_key, timeout=self.timeout)

    async def validate_config(self) -> bool:
        """Validate Groq configuration."""
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")

        if not self.api_key.startswith("gsk_"):
            raise ValueError("GROQ_API_KEY format is invalid (should start with 'gsk_')")

        return True

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the configured Groq model."""
        return {
            "model_name": self.model,
            "provider": "groq",
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
        """Send messages to Groq and get response.

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
                logger.debug(f"Groq API call (attempt {attempt + 1}/{self.max_retries})")

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=full_messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                response_text = response.choices[0].message.content or ""

                # Use actual token counts from API response if available
                prompt_tokens = getattr(response.usage, "prompt_tokens", 0)
                completion_tokens = getattr(response.usage, "completion_tokens", 0)
                tokens_used = prompt_tokens + completion_tokens

                logger.debug(
                    f"Groq response received: {len(response_text)} chars, {tokens_used} tokens"
                )
                return response_text, tokens_used

            except Exception as e:
                last_error = e
                err_str = str(e)

                # Check for rate limit errors
                is_rate_limit = "429" in err_str or "rate_limit" in err_str.lower()
                if is_rate_limit:
                    logger.error(f"Groq rate limit error (no retry): {e}")
                    raise

                logger.warning(f"Groq API error (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2**attempt)
                    await asyncio.sleep(wait_time)

        logger.error(f"Groq API failed after {self.max_retries} attempts: {last_error}")
        raise last_error or Exception("Groq API call failed")
