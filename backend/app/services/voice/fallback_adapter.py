"""Fallback adapter for voice providers with automatic failover."""

import logging
from typing import Any

from app.services.voice.provider_factory import VoiceProviderFactory
from app.services.voice.providers.base import (
    VoiceProvider,
    VoiceProviderError,
    VoiceCloneRequest,
    VoiceCloneResponse,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)

logger = logging.getLogger(__name__)


class VoiceProviderFallbackAdapter:
    """
    Fallback adapter that tries multiple voice providers in order.

    If one provider fails, it automatically tries the next one in the list.
    This ensures high availability for voice synthesis.
    """

    def __init__(self, provider_configs: list[dict[str, Any]]):
        """
        Initialize fallback adapter with provider configurations.

        Args:
            provider_configs: List of provider configs in priority order.
                Each config should have: {"name": "provider_name", "config": {...}}

        Example:
            provider_configs = [
                {"name": "elevenlabs", "config": {"api_key": "..."}},
                {"name": "cartesia", "config": {"api_key": "..."}},
                {"name": "deepgram", "config": {"api_key": "..."}},
                {"name": "coqui_xtts", "config": {}},
            ]
        """
        self.provider_configs = provider_configs
        self.providers: list[VoiceProvider] = []

        # Initialize all providers
        for provider_config in provider_configs:
            try:
                provider = VoiceProviderFactory.create_provider(
                    provider_config["name"], provider_config["config"]
                )
                self.providers.append(provider)
                logger.info(f"Initialized fallback provider: {provider_config['name']}")
            except Exception as e:
                logger.warning(
                    f"Failed to initialize provider {provider_config['name']}: {e}"
                )

        if not self.providers:
            raise ValueError("No voice providers could be initialized")

        logger.info(
            f"Fallback adapter initialized with {len(self.providers)} providers"
        )

    async def synthesize_speech(
        self, request: VoiceSynthesisRequest
    ) -> VoiceSynthesisResponse:
        """
        Synthesize speech with automatic fallback.

        Tries each provider in order until one succeeds.
        """
        last_error = None

        for i, provider in enumerate(self.providers):
            try:
                logger.info(
                    f"Attempting synthesis with provider {i+1}/{len(self.providers)}: "
                    f"{provider.provider_name}"
                )

                response = await provider.synthesize_speech(request)

                logger.info(
                    f"✓ Synthesis successful with provider: {provider.provider_name}"
                )

                return response

            except VoiceProviderError as e:
                last_error = e
                logger.warning(
                    f"✗ Provider {provider.provider_name} failed: {e}. "
                    f"Trying next provider..."
                )
                continue

            except Exception as e:
                last_error = e
                logger.error(
                    f"✗ Unexpected error with provider {provider.provider_name}: {e}. "
                    f"Trying next provider..."
                )
                continue

        # All providers failed
        logger.error(
            f"All {len(self.providers)} providers failed for speech synthesis"
        )
        raise VoiceProviderError(
            f"All voice providers failed. Last error: {last_error}"
        ) from last_error

    async def clone_voice(self, request: VoiceCloneRequest) -> VoiceCloneResponse:
        """
        Clone voice with automatic fallback.

        Tries each provider that supports voice cloning.
        """
        last_error = None
        attempted = 0

        for provider in self.providers:
            try:
                logger.info(f"Attempting voice cloning with: {provider.provider_name}")

                response = await provider.clone_voice(request)

                logger.info(
                    f"✓ Voice cloning successful with provider: {provider.provider_name}"
                )

                return response

            except VoiceProviderError as e:
                last_error = e
                attempted += 1

                # Check if this is a "not supported" error
                if "not supported" in str(e).lower():
                    logger.info(
                        f"Provider {provider.provider_name} does not support voice cloning. "
                        f"Trying next provider..."
                    )
                else:
                    logger.warning(
                        f"✗ Provider {provider.provider_name} failed: {e}. "
                        f"Trying next provider..."
                    )
                continue

            except Exception as e:
                last_error = e
                attempted += 1
                logger.error(
                    f"✗ Unexpected error with provider {provider.provider_name}: {e}. "
                    f"Trying next provider..."
                )
                continue

        # All providers failed
        logger.error(
            f"All {attempted} providers failed or don't support voice cloning"
        )
        raise VoiceProviderError(
            f"Voice cloning failed with all providers. Last error: {last_error}"
        ) from last_error

    async def list_voices(self, language: str | None = None) -> dict[str, list[dict]]:
        """
        List voices from all providers.

        Returns:
            Dict mapping provider name to list of voices
        """
        all_voices = {}

        for provider in self.providers:
            try:
                voices = await provider.list_voices(language)
                all_voices[provider.provider_name] = voices
                logger.info(
                    f"Retrieved {len(voices)} voices from {provider.provider_name}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to list voices from {provider.provider_name}: {e}"
                )
                all_voices[provider.provider_name] = []

        return all_voices

    def get_provider_status(self) -> dict[str, dict]:
        """
        Get status of all providers.

        Returns:
            Dict with provider status information
        """
        status = {}

        for i, provider in enumerate(self.providers):
            status[provider.provider_name] = {
                "priority": i + 1,
                "total_providers": len(self.providers),
                "name": provider.provider_name,
                "initialized": True,
            }

        return status


def create_fallback_adapter(config: dict[str, Any]) -> VoiceProviderFallbackAdapter:
    """
    Create fallback adapter from configuration.

    Example config:
    {
        "providers": [
            {"name": "elevenlabs", "api_key": "..."},
            {"name": "cartesia", "api_key": "..."},
            {"name": "deepgram", "api_key": "..."},
            {"name": "coqui_xtts"},
        ]
    }
    """
    provider_configs = []

    for provider_config in config.get("providers", []):
        name = provider_config.pop("name")
        provider_configs.append({"name": name, "config": provider_config})

    return VoiceProviderFallbackAdapter(provider_configs)
