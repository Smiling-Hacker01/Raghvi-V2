from abc import ABC, abstractmethod
from typing import Any


class AIProviderAdapter(ABC):
    """Abstract interface for LLM providers.

    All LLM providers (OpenAI, Anthropic, local models) must implement
    this interface. Business logic only touches this interface, never
    the concrete provider implementations.
    """

    @abstractmethod
    async def send_message(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> tuple[str, int]:
        """Send messages to LLM and get response.

        Args:
            messages: List of message dicts {"role": "user"/"assistant", "content": "..."}
            system_prompt: System prompt to establish context/personality
            max_tokens: Max tokens in response
            temperature: Sampling temperature (0-1, higher = more creative)

        Returns:
            Tuple of (response_text, tokens_used)

        Raises:
            Exception: If LLM call fails (timeout, auth error, etc.)
        """
        pass

    @abstractmethod
    async def validate_config(self) -> bool:
        """Validate that provider is properly configured.

        Returns:
            True if valid, False if missing credentials/config

        Raises:
            ValueError: If configuration is invalid
        """
        pass

    @abstractmethod
    def get_model_info(self) -> dict[str, Any]:
        """Get information about the configured model.

        Returns:
            Dict with keys like:
            - model_name: str (e.g., "gpt-4-turbo")
            - provider: str (e.g., "openai")
            - max_tokens: int
            - cost_per_1k_tokens: float (optional, for tracking)
        """
        pass
