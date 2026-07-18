import logging

from app.core.config import get_settings
from app.services.ai.adapter import AIProviderAdapter

logger = logging.getLogger(__name__)


class AIProviderChain:
    """Multi-provider failover chain.

    Tries providers in order. If one fails (quota, timeout, error),
    silently falls back to next provider. User never knows.

    System prompt and context are passed to every provider attempt,
    ensuring consistent Raghvi personality regardless of which model responds.
    """

    def __init__(self):
        settings = get_settings()
        self.primary_provider = settings.ai_provider.lower()

        logger.info("=" * 60)
        logger.info("Initializing AIProviderChain")
        logger.info(f"Primary provider configured: {self.primary_provider}")
        logger.info(f"OpenAI API key present: {bool(settings.openai_api_key)}")
        logger.info(f"Gemini API key present: {bool(settings.gemini_api_key)}")
        logger.info("=" * 60)

        # Build provider chain (order matters)
        self.provider_chain = self._build_chain()

        if not self.provider_chain:
            raise ValueError(
                f"No valid AI providers configured. "
                f"Primary: {self.primary_provider}. "
                f"Please configure at least one AI provider API key."
            )

        logger.info(f"Provider chain ready with: {self.get_available_providers()}")

    def _build_chain(self) -> list[tuple[str, AIProviderAdapter]]:
        """Build provider chain in order of preference.

        Returns:
            List of (provider_name, adapter) tuples in order to try
        """
        chain = []
        primary = self.primary_provider

        logger.info(f"Building provider chain starting with primary: {primary}")

        # Try to load primary provider first
        try:
            logger.info(f"Loading primary provider: {primary}")
            adapter = self._load_provider(primary)
            if adapter:
                chain.append((primary, adapter))
                logger.info(f"✓ Successfully loaded primary provider: {primary}")
            else:
                logger.warning(
                    f"Primary provider {primary} not configured (API key missing or invalid)"
                )
        except Exception as e:
            logger.error(
                f"Failed to load primary provider {primary}: {type(e).__name__}: {str(e)[:100]}"
            )

        # Add fallback providers (any not already in chain)
        fallback_order = ["openai", "gemini"]
        for provider in fallback_order:
            if provider == primary:
                # Skip primary, already attempted
                continue

            try:
                logger.info(f"Attempting to load fallback provider: {provider}")
                adapter = self._load_provider(provider)
                if adapter:
                    chain.append((provider, adapter))
                    logger.info(f"✓ Successfully loaded fallback provider: {provider}")
                else:
                    logger.info(
                        f"Fallback provider {provider} not configured (API key missing or invalid)"
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to load fallback provider {provider}: "
                    f"{type(e).__name__}: {str(e)[:100]}"
                )

        logger.info(f"Final provider chain: {[name for name, _ in chain]}")
        return chain

    def _load_provider(self, provider_name: str) -> AIProviderAdapter | None:
        """Load a specific provider adapter.

        Args:
            provider_name: Name of provider (openai, gemini)

        Returns:
            Adapter instance if valid and configured, None if not configured

        Raises:
            Exception: If provider is configured but fails to load
        """
        settings = get_settings()
        provider_name = provider_name.lower()

        if provider_name == "openai":
            logger.debug("Checking OpenAI configuration...")
            if not settings.openai_api_key:
                logger.debug("OpenAI API key not configured")
                return None

            logger.debug("Loading OpenAI adapter...")
            try:
                from app.services.ai.providers.openai import OpenAIAdapter

                adapter = OpenAIAdapter()
                logger.debug(f"OpenAI adapter loaded: model={adapter.model}")
                return adapter
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI adapter: {e}")
                raise

        elif provider_name == "gemini":
            logger.debug("Checking Gemini configuration...")
            if not settings.gemini_api_key:
                logger.debug("Gemini API key not configured")
                return None

            logger.debug("Loading Gemini adapter...")
            try:
                from app.services.ai.providers.gemini import GeminiAdapter

                adapter = GeminiAdapter()
                logger.debug(f"Gemini adapter loaded: model={adapter.model}")
                return adapter
            except Exception as e:
                logger.error(f"Failed to initialize Gemini adapter: {e}")
                raise

        logger.warning(f"Unknown provider: {provider_name}")
        return None

    async def send_message(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> tuple[str, int, str]:
        """Send message with automatic failover to next provider on error.

        User never knows which model responds. Same system prompt (Raghvi personality)
        is used for every attempt, ensuring consistent voice.

        Args:
            messages: Conversation history
            system_prompt: System prompt (Raghvi's personality)
            max_tokens: Max tokens in response
            temperature: Sampling temperature

        Returns:
            Tuple of (response_text, tokens_used, provider_used)

        Raises:
            RuntimeError: Only if ALL providers fail
        """
        if not self.provider_chain:
            logger.error("No AI providers available in chain")
            raise ValueError("No AI providers available")

        last_error = None
        attempted_providers = []

        # Try each provider in chain
        for provider_name, adapter in self.provider_chain:
            attempted_providers.append(provider_name)
            try:
                logger.debug(f"Attempting to send message via: {provider_name}")

                response, tokens = await adapter.send_message(
                    messages=messages,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                logger.info(
                    f"✓ Message successfully generated via {provider_name} ({tokens} tokens)"
                )
                return response, tokens, provider_name

            except Exception as e:
                last_error = e
                logger.debug(
                    f"Provider {provider_name} failed "
                    f"({type(e).__name__}): {str(e)[:100]}. "
                    f"Attempting next provider..."
                )

        # All providers failed
        logger.error(
            f"All AI providers exhausted. "
            f"Attempted: {attempted_providers}. "
            f"Last error: {type(last_error).__name__}: {str(last_error)[:100]}"
        )
        raise RuntimeError(
            "All AI providers failed to respond. Please try again in a moment."
        ) from last_error

    def get_available_providers(self) -> list[str]:
        """Get list of available AI providers.

        Returns:
            List of provider names currently configured and available
            (e.g., ["openai", "gemini"])
        """
        return [name for name, _ in self.provider_chain]
