from app.services.ai.registry import AIProviderRegistry


class AIClient:
    """Business logic client for AI/LLM operations.

    This class encapsulates chat logic:
    - Building system prompts
    - Managing conversation context
    - Calling the LLM via adapter (provider-agnostic)
    - Error handling and retries

    Never touches provider-specific code directly.
    """

    def __init__(self):
        self.adapter = AIProviderRegistry.get_adapter()

    async def send_message(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> tuple[str, int]:
        """Send a message to Raghvi and get response.

        Args:
            messages: Conversation history (last 20 messages)
            system_prompt: System prompt with user context + memories
            max_tokens: Max tokens in response
            temperature: Sampling temperature

        Returns:
            Tuple of (response_text, tokens_used)

        Raises:
            Exception: If LLM call fails (wrapped with friendly error)
        """
        return await self.adapter.send_message(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def get_model_info(self) -> dict:
        """Get info about the currently configured LLM model."""
        return self.adapter.get_model_info()
