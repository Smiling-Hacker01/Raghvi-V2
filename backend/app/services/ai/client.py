import logging

from app.services.ai.errors import AIConfigurationError, AIProviderFailureError
from app.services.ai.chain import AIProviderChain

logger = logging.getLogger(__name__)


class AIClient:
    """Business logic client for AI/LLM operations.

    Uses AIProviderChain for automatic failover across multiple LLM providers.
    User never knows which model is responding - always Raghvi.
    
    Encapsulates chat logic:
    - Building system prompts
    - Managing conversation context
    - Calling the LLM via provider chain (automatic failover)
    - Error handling with friendly responses
    
    Never touches provider-specific code directly.
    """

    def __init__(self):
        try:
            self.chain = AIProviderChain()
        except ValueError as exc:
            logger.error(f"Failed to initialize AI provider chain: {exc}")
            raise AIConfigurationError(
                "I'm having trouble getting started. Please check your AI provider configuration.",
                cause=exc,
            ) from exc

    async def send_message(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> tuple[str, int, str]:
        """Send a message to Raghvi and get response with automatic failover.

        If primary provider fails (quota, timeout, error), seamlessly tries
        next provider. User never knows. Same system prompt ensures Raghvi
        personality is preserved across all provider attempts.

        Args:
            messages: Conversation history (last 20 messages)
            system_prompt: System prompt with user context + memories + Raghvi personality
            max_tokens: Max tokens in response
            temperature: Sampling temperature

        Returns:
            Tuple of (response_text, tokens_used, provider_used)
            
            Note: provider_used is for internal logging only.
                  Never expose this to the user.

        Raises:
            AIConfigurationError: If no providers are configured
            AIProviderFailureError: If all providers fail to respond
        """
        if not self.chain.provider_chain:
            logger.error("No AI providers available")
            raise AIConfigurationError(
                "Sorry, I'm not available right now. Try again in a moment?",
                cause=ValueError("No AI providers configured"),
            )

        try:
            response, tokens, provider = await self.chain.send_message(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            
            # Log which provider was used (internal only, for monitoring)
            logger.info(f"Message generated via AI provider: {provider}")
            
            return response, tokens, provider

        except RuntimeError as exc:
            # AIProviderChain raises RuntimeError when all providers fail
            logger.error(f"All AI providers exhausted: {exc}")
            raise AIProviderFailureError(
                "My mind just went blank. Can you try that again in a moment?",
                cause=exc,
            ) from exc

        except AIProviderFailureError:
            # Re-raise our custom exception as-is
            raise

        except Exception as exc:
            # Catch any unexpected errors
            logger.exception(f"Unexpected error in AI client: {exc}")
            raise AIProviderFailureError(
                "Something's not quite right with me. Give me a second?",
                cause=exc,
            ) from exc

    def get_available_providers(self) -> list[str]:
        """Get list of available AI providers.
        
        For internal monitoring/logging only.
        Never expose to user.
        
        Returns:
            List of provider names (e.g., ["openai", "gemini"])
        """
        return self.chain.get_available_providers()

    def get_model_info(self) -> dict:
        """Get info about the primary AI model (for internal use only).
        
        Note: Since we use automatic failover, this returns info about
        the PRIMARY provider only. Fallback providers may have different specs.
        
        Never expose this to user.
        """
        if not self.chain.provider_chain:
            return {"error": "No providers available"}
        
        primary_name, primary_adapter = self.chain.provider_chain[0]
        return {
            **primary_adapter.get_model_info(),
            "available_providers": self.get_available_providers(),
        }