import os
from importlib import import_module

from app.services.ai.adapter import AIProviderAdapter


class AIProviderRegistry:
    """Registry for LLM provider adapters.

    Loads the correct adapter based on AI_PROVIDER environment variable.
    New providers can be added without changing this registry (plugin pattern).
    """

    _adapters: dict[str, type[AIProviderAdapter]] = {}
    _instance: AIProviderAdapter | None = None

    @classmethod
    def register(cls, provider_name: str, adapter_class: type[AIProviderAdapter]) -> None:
        """Register a new provider adapter.

        Args:
            provider_name: Name of provider (e.g., "openai", "anthropic")
            adapter_class: Adapter class (subclass of AIProviderAdapter)
        """
        cls._adapters[provider_name.lower()] = adapter_class

    @classmethod
    def get_adapter(cls) -> AIProviderAdapter:
        """Get the configured LLM provider adapter.

        Returns:
            Instantiated adapter for the configured provider

        Raises:
            ValueError: If provider not configured or not registered
        """
        if cls._instance is not None:
            return cls._instance

        provider = os.getenv("AI_PROVIDER", "openai").lower()

        if provider not in cls._adapters:
            raise ValueError(
                f"Unknown AI provider: {provider}. "
                f"Registered providers: {list(cls._adapters.keys())}"
            )

        adapter_class = cls._adapters[provider]
        cls._instance = adapter_class()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (useful for testing)."""
        cls._instance = None


# Auto-register built-in providers on import
def _register_builtin_providers() -> None:
    """Register default providers. Called at module import."""
    try:
        from app.services.ai.providers.openai import OpenAIAdapter
        AIProviderRegistry.register("openai", OpenAIAdapter)
    except ImportError:
        pass

    try:
        from app.services.ai.providers.gemini import GeminiAdapter
        AIProviderRegistry.register("gemini", GeminiAdapter)
    except ImportError:
        pass


_register_builtin_providers()
