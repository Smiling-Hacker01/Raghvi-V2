import asyncio
import logging
from typing import Any

from huggingface_hub import AsyncInferenceClient

from app.core.config import get_settings
from app.services.ai.adapter import AIProviderAdapter

logger = logging.getLogger(__name__)


class HuggingFaceAdapter(AIProviderAdapter):
    """HuggingFace Inference API adapter.

    Implements AIProviderAdapter for HuggingFace's serverless inference API.
    """

    def __init__(self):
        settings = get_settings()

        self.api_key = settings.hugging_face_api_key
        self.model = settings.hugging_face_model
        self.timeout = settings.hugging_face_timeout_seconds
        self.max_retries = 3
        self.retry_delay = 1

        self.client = AsyncInferenceClient(token=self.api_key, timeout=self.timeout)

    async def validate_config(self) -> bool:
        """Validate HuggingFace configuration."""
        if not self.api_key:
            raise ValueError("HUGGING_FACE_API_KEY environment variable not set")

        if not self.api_key.startswith("hf_"):
            raise ValueError("HUGGING_FACE_API_KEY format is invalid (should start with 'hf_')")

        return True

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the configured HuggingFace model."""
        return {
            "model_name": self.model,
            "provider": "huggingface",
            "max_tokens": 4096,
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
        """Send messages to HuggingFace and get response.

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
        # Format messages for HuggingFace chat completion
        full_messages = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        last_error = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"HuggingFace API call (attempt {attempt + 1}/{self.max_retries})")

                response = await self.client.chat_completion(
                    model=self.model,
                    messages=full_messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                # Extract response text
                response_text = response.choices[0].message.content or ""

                # Calculate token usage
                prompt_text = system_prompt + "\n".join(m.get("content", "") for m in messages)
                tokens_used = self._count_tokens(prompt_text) + self._count_tokens(response_text)

                logger.debug(
                    f"HuggingFace response received: {len(response_text)} chars, "
                    f"~{tokens_used} tokens"
                )
                return response_text, tokens_used

            except Exception as e:
                last_error = e
                err_str = str(e)

                # Check for rate limit or quota errors
                is_rate_limit = (
                    "429" in err_str
                    or "rate limit" in err_str.lower()
                    or "quota" in err_str.lower()
                )
                if is_rate_limit:
                    logger.error(f"HuggingFace rate limit/quota error (no retry): {e}")
                    raise

                logger.warning(
                    f"HuggingFace API error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2**attempt)
                    await asyncio.sleep(wait_time)

        logger.error(f"HuggingFace API failed after {self.max_retries} attempts: {last_error}")
        raise last_error or Exception("HuggingFace API call failed")
