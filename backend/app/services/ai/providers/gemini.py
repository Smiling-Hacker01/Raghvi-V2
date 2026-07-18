import asyncio
import logging
from typing import Any

from google.genai import Client
from google.genai.types import GenerateContentConfig

from app.core.config import get_settings
from app.services.ai.adapter import AIProviderAdapter

logger = logging.getLogger(__name__)


class GeminiAdapter(AIProviderAdapter):
    """Google Gemini provider adapter.
    
    Implements AIProviderAdapter for Google's Gemini API (google-genai v0.3+).
    """

    def __init__(self):
        settings = get_settings()
        
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model
        self.timeout = settings.gemini_timeout_seconds
        self.max_retries = 3
        self.retry_delay = 1

        # Initialize Gemini client with API key
        self.client = Client(api_key=self.api_key)

    async def validate_config(self) -> bool:
        """Validate Gemini configuration."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")

        if not self.api_key.startswith("AIzaSy"):
            raise ValueError(
                "GEMINI_API_KEY format is invalid (should start with 'AIzaSy')"
            )

        return True

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the configured Gemini model."""
        return {
            "model_name": self.model,
            "provider": "gemini",
            "max_tokens": 8192,
            "timeout_seconds": self.timeout,
        }

    def _count_tokens(self, text: str) -> int:
        """Estimate token count (Gemini doesn't expose token counter easily)."""
        # Rough estimate: ~4 chars per token (varies by model)
        return len(text) // 4

    async def send_message(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> tuple[str, int]:
        """Send messages to Gemini and get response.
        
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
        last_error = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"Gemini API call (attempt {attempt + 1}/{self.max_retries})"
                )

                # Build message history for Gemini
                # Format: combine system prompt + conversation
                conversation_text = system_prompt + "\n\n"
                for msg in messages:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    conversation_text += f"{role}: {content}\n"

                # Add prompt for response
                conversation_text += "assistant: "

                # Call Gemini API (using asyncio.to_thread for sync->async)
                response = await asyncio.to_thread(
                    self._call_gemini,
                    conversation_text,
                    max_tokens,
                    temperature,
                )

                response_text = response or ""
                tokens_used = (
                    self._count_tokens(conversation_text)
                    + self._count_tokens(response_text)
                )

                logger.debug(
                    f"Gemini response received: {len(response_text)} chars, "
                    f"~{tokens_used} tokens"
                )
                return response_text, tokens_used

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Gemini API error (attempt {attempt + 1}/{self.max_retries}): "
                    f"{type(e).__name__}: {str(e)[:100]}"
                )
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    await asyncio.sleep(wait_time)

        # All retries exhausted
        logger.error(
            f"Gemini API failed after {self.max_retries} attempts: {last_error}"
        )
        raise last_error or Exception("Gemini API call failed")

    def _call_gemini(
        self, prompt: str, max_tokens: int, temperature: float
    ) -> str:
        """Synchronous wrapper for Gemini API call.
        
        Called via asyncio.to_thread() to avoid blocking.
        """
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                    top_p=0.95,
                ),
            )
            
            return response.text if response else ""
        except Exception as e:
            logger.error(f"Gemini generate_content failed: {e}")
            raise