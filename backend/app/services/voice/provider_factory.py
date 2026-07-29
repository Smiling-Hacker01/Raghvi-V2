"""Factory for creating voice provider instances."""

import logging
from typing import Any

from app.services.voice.providers.base import VoiceProvider, VoiceProviderError
from app.services.voice.providers.cartesia import CartesiaProvider
from app.services.voice.providers.coqui import CoquiProvider
from app.services.voice.providers.coqui_xtts import CoquiXTTSProvider
from app.services.voice.providers.deepgram import DeepgramProvider
from app.services.voice.providers.elevenlabs import ElevenLabsProvider
from app.services.voice.providers.nvidia import NvidiaProvider

logger = logging.getLogger(__name__)


class VoiceProviderFactory:
    """Factory for creating voice provider instances."""

    _providers: dict[str, type[VoiceProvider]] = {
        "elevenlabs": ElevenLabsProvider,
        "coqui": CoquiProvider,
        "cartesia": CartesiaProvider,
        "deepgram": DeepgramProvider,
        "nvidia": NvidiaProvider,
        "coqui_xtts": CoquiXTTSProvider,
    }

    @classmethod
    def create_provider(
        cls,
        provider_name: str,
        config: dict[str, Any],
    ) -> VoiceProvider:
        """Create a voice provider instance."""

        provider_class = cls._providers.get(provider_name)

        if not provider_class:
            raise VoiceProviderError(
                f"Unknown voice provider: {provider_name}. "
                f"Available: {', '.join(cls._providers.keys())}"
            )

        try:
            provider = provider_class(config)
            logger.info(f"Created voice provider: {provider_name}")
            return provider

        except Exception as e:
            logger.error(f"Failed to create provider {provider_name}: {e}")
            raise VoiceProviderError(f"Failed to create provider {provider_name}: {e}") from e

    @classmethod
    def register_provider(
        cls,
        name: str,
        provider_class: type[VoiceProvider],
    ) -> None:
        """Register a new voice provider."""
        cls._providers[name] = provider_class
        logger.info(f"Registered voice provider: {name}")

    @classmethod
    def list_providers(cls) -> list[str]:
        """List available provider names."""
        return list(cls._providers.keys())
