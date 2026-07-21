import asyncio
import logging
from typing import Any

import tiktoken
from openai import (
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
)

from app.core.config import get_settings
from app.services.ai.adapter import AIProviderAdapter

logger = logging.getLogger(__name__)


class OpenAIAdapter(AIProviderAdapter):
    """OpenAI provider adapter.

    Implements AIProviderAdapter for OpenAI's API.
    Handles token counting, retry logic, error handling.
    """

    def __init__(self):
        settings = get_settings()

        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.timeout = settings.openai_timeout_seconds
        self.max_retries = 3
        self.retry_delay = 1

        self.client = AsyncOpenAI(api_key=self.api_key, timeout=self.timeout)

        try:
            self.encoder = tiktoken.encoding_for_model(self.model)
        except KeyError:
            self.encoder = tiktoken.get_encoding("cl100k_base")

    async def validate_config(self) -> bool:
        """Validate OpenAI configuration."""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        if not self.api_key.startswith("sk-"):
            raise ValueError("OPENAI_API_KEY format is invalid (should start with 'sk-')")

        return True

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the configured OpenAI model."""
        return {
            "model_name": self.model,
            "provider": "openai",
            "max_tokens": 8192 if "gpt-4" in self.model else 4096,
            "timeout_seconds": self.timeout,
        }

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken encoder."""
        try:
            tokens = self.encoder.encode(text)
            return len(tokens)
        except Exception as e:
            logger.warning(f"Failed to count tokens: {e}, using estimate")
            # Rough estimate: ~4 chars per token
            return len(text) // 4

    def _build_token_count(self, messages: list[dict[str, str]], response: str) -> int:
        """Estimate total tokens used (messages + response).

        Note: OpenAI API returns exact token counts in the response,
        but for now we estimate for simplicity. Can be updated to use
        actual API response counts later.
        """
        messages_text = "\n".join(m.get("content", "") for m in messages)
        messages_tokens = self._count_tokens(messages_text)
        response_tokens = self._count_tokens(response)
        return messages_tokens + response_tokens

    async def send_message(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> tuple[str, int]:
        """Send messages to OpenAI and get response.

        Implements retry logic with exponential backoff for transient errors.

        Args:
            messages: Conversation history
            system_prompt: System prompt for personality/context
            max_tokens: Max tokens in response
            temperature: Sampling temperature

        Returns:
            Tuple of (response_text, tokens_used)

        Raises:
            Exception: If all retries fail
        """
        # Prepare messages with system prompt
        full_messages = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        last_error = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"OpenAI API call (attempt {attempt + 1}/{self.max_retries})")

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=full_messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                # Extract response text
                response_text = response.choices[0].message.content or ""
                tokens_used = self._build_token_count(messages, response_text)

                logger.debug(
                    f"OpenAI response received: {len(response_text)} chars, {tokens_used} tokens"
                )
                return response_text, tokens_used

            except APITimeoutError as e:
                last_error = e
                logger.warning(f"OpenAI timeout (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2**attempt)
                    await asyncio.sleep(wait_time)

            except RateLimitError as e:
                logger.error(f"OpenAI 429 RateLimit / quota error (no retry): {e}")
                raise

            except AuthenticationError as e:
                logger.error(f"OpenAI authentication failed: {e}")
                raise ValueError(
                    "I can't get into my account connection right now. "
                    "Please check back in a moment?"
                ) from e

            except NotFoundError as e:
                logger.error(f"OpenAI model not found: {e}")
                raise ValueError(
                    "I'm pointed at a model I can't reach right now. "
                    "Give me a moment and try again?"
                ) from e

            except APIError as e:
                last_error = e
                logger.error(f"OpenAI API error (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2**attempt)
                    await asyncio.sleep(wait_time)

        # All retries exhausted
        logger.error(f"OpenAI API failed after {self.max_retries} attempts: {last_error}")
        raise last_error or Exception("OpenAI API call failed")
