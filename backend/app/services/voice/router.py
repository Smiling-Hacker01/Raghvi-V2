"""Vendor-agnostic Voice Router for intelligent, capability-aware routing and failover."""

import asyncio
import logging
from typing import Any

from app.services.voice.providers.base import (
    ProviderCapabilities,
    VoiceCapability,
    VoiceCloneRequest,
    VoiceCloneResponse,
    VoiceProvider,
    VoiceProviderError,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)

logger = logging.getLogger(__name__)

# Canonical Indian language codes supported by Indic speech models
INDIC_LANGUAGES = {"as", "bn", "gu", "hi", "kn", "ml", "mr", "or", "pa", "ta", "te", "hinglish"}


class VoiceRouter:
    """
    Intelligent voice router and dispatcher.

    Routes speech synthesis and voice cloning requests based on:
    - Target language and locale
    - Required voice capabilities (TTS, voice cloning, zero-shot cloning, streaming)
    - Configured provider priority and user preferences
    - Provider readiness and health status
    - Explicit, deterministic failover without silent intent degradation
    """

    def __init__(
        self,
        providers: list[VoiceProvider] | None = None,
        default_language: str = "en",
        request_timeout_seconds: float = 30.0,
    ):
        self.providers: list[VoiceProvider] = providers or []
        self.default_language = default_language
        self.request_timeout_seconds = request_timeout_seconds

    def register_provider(self, provider: VoiceProvider) -> None:
        """Register a new provider instance."""
        # Replace existing provider with same name if already present
        for i, p in enumerate(self.providers):
            if p.provider_name == provider.provider_name:
                self.providers[i] = provider
                logger.info(f"Updated registered provider: {provider.provider_name}")
                return
        self.providers.append(provider)
        logger.info(f"Registered voice provider: {provider.provider_name}")

    def get_provider(self, name: str) -> VoiceProvider | None:
        """Get a registered provider by name."""
        for provider in self.providers:
            if provider.provider_name == name:
                return provider
        return None

    def get_capabilities_map(self) -> dict[str, ProviderCapabilities]:
        """Return a mapping of provider name to its declared capabilities."""
        caps_map = {}
        for p in self.providers:
            if hasattr(p, "get_capabilities"):
                caps_map[p.provider_name] = p.get_capabilities()
            else:
                caps_map[p.provider_name] = ProviderCapabilities(
                    capabilities={VoiceCapability.TEXT_TO_SPEECH, VoiceCapability.VOICE_CLONING},
                    supported_languages={"*"},
                )
        return caps_map

    async def check_health_all(self) -> dict[str, dict[str, Any]]:
        """Run health and readiness checks across all registered providers."""
        results = {}
        for provider in self.providers:
            try:
                if hasattr(provider, "check_health"):
                    status = await provider.check_health()
                else:
                    status = {
                        "status": "ready",
                        "provider": getattr(provider, "provider_name", "unknown"),
                        "is_commercial_ready": True,
                        "capabilities": [VoiceCapability.TEXT_TO_SPEECH.value],
                    }
                results[provider.provider_name] = status
            except Exception as e:
                logger.warning(f"Health check failed for {provider.provider_name}: {e}")
                results[provider.provider_name] = {
                    "status": "unhealthy",
                    "provider": provider.provider_name,
                    "error": str(e),
                }
        return results

    def find_compatible_providers(
        self,
        language: str,
        required_capability: VoiceCapability = VoiceCapability.TEXT_TO_SPEECH,
        preferred_provider: str | None = None,
    ) -> list[VoiceProvider]:
        """
        Find and sort compatible providers for the given language and capability.

        Ordering priority:
        1. Explicitly preferred provider (if it supports the capability and language)
        2. Domain-specialized providers:
           - For Indian languages: IndicF5 (if available and capable)
           - For English/other: Coqui XTTS, EdgeTTS, ElevenLabs, Cartesia, Deepgram
        3. General providers in configured order
        """
        lang_code = language.lower().split("-")[0].strip()
        is_indic = lang_code in INDIC_LANGUAGES

        compatible: list[VoiceProvider] = []
        for provider in self.providers:
            if hasattr(provider, "get_capabilities"):
                caps = provider.get_capabilities()
            else:
                caps = ProviderCapabilities(
                    capabilities={
                        VoiceCapability.TEXT_TO_SPEECH,
                        VoiceCapability.VOICE_CLONING,
                    },
                    supported_languages={"*"},
                )
            if not caps.supports(required_capability):
                continue
            if not caps.supports_language(lang_code):
                continue
            compatible.append(provider)

        # Sort candidate providers intelligently
        def sort_key(p: VoiceProvider) -> tuple[int, int]:
            name = p.provider_name
            # Rank 0: Preferred provider
            if preferred_provider and name == preferred_provider:
                return (0, 0)
            # Rank 1: Domain-optimal provider
            if is_indic and name == "indicf5":
                return (1, 0)
            if not is_indic and name in ("coqui_xtts", "coqui"):
                return (1, 1)
            # Rank 2: High-fidelity multilingual providers
            if name == "edge_tts":
                return (2, 0)
            if name == "elevenlabs":
                return (2, 1)
            if name == "cartesia":
                return (2, 2)
            if name == "deepgram":
                return (2, 3)
            # Rank 3: Other providers
            return (3, 0)

        compatible.sort(key=sort_key)
        return compatible

    async def synthesize_speech(
        self,
        request: VoiceSynthesisRequest,
        preferred_provider: str | None = None,
    ) -> VoiceSynthesisResponse:
        """
        Synthesize speech with language/capability matching and deterministic failover.

        Raises VoiceProviderError if no compatible provider exists or all fail.
        """
        candidates = self.find_compatible_providers(
            language=request.language,
            required_capability=VoiceCapability.TEXT_TO_SPEECH,
            preferred_provider=preferred_provider,
        )

        if not candidates:
            raise VoiceProviderError(
                f"No voice provider supports TTS for language '{request.language}'"
            )

        # Cleanse markdown, emojis, and code formatting for consistent speech synthesis
        from app.services.voice.text_normalizer import clean_text_for_speech

        is_hindi = request.language.lower().startswith("hi") or any(
            "\u0900" <= ch <= "\u097f" for ch in request.text
        )
        cleaned_text = clean_text_for_speech(request.text, is_hindi=is_hindi)
        if not cleaned_text.strip():
            cleaned_text = "जी, समझ गई।" if is_hindi else "I understand."

        sanitized_request = VoiceSynthesisRequest(
            text=cleaned_text,
            voice_id=request.voice_id,
            language=request.language,
            emotion=request.emotion,
            speed=request.speed,
        )

        last_error = None
        for i, provider in enumerate(candidates):
            try:
                logger.info(
                    f"Routing TTS [{sanitized_request.language}] to {provider.provider_name} "
                    f"({i + 1}/{len(candidates)})"
                )
                async with asyncio.timeout(self.request_timeout_seconds):
                    response = await provider.synthesize_speech(sanitized_request)
                    if response.provider is None:
                        response.provider = provider.provider_name
                    logger.info(
                        f"Speech synthesis succeeded with provider {provider.provider_name}"
                    )
                    return response
            except TimeoutError:
                last_error = VoiceProviderError(
                    f"Provider {provider.provider_name} timed out after "
                    f"{self.request_timeout_seconds}s"
                )
                logger.warning(f"Timeout on provider {provider.provider_name}, trying next...")
            except VoiceProviderError as e:
                last_error = e
                logger.warning(
                    f"Provider {provider.provider_name} failed: {e}. Trying next provider..."
                )
            except Exception as e:
                last_error = VoiceProviderError(
                    f"Unexpected error in {provider.provider_name}: {e}"
                )
                logger.error(
                    f"Unexpected error in {provider.provider_name}: {e}. Trying next provider..."
                )

        raise VoiceProviderError(
            f"All compatible voice providers failed for language '{request.language}'. "
            f"Last error: {last_error}"
        ) from last_error

    async def clone_voice(
        self,
        request: VoiceCloneRequest,
        preferred_provider: str | None = None,
    ) -> VoiceCloneResponse:
        """
        Execute voice cloning with explicit consent verification and capability routing.

        Raises VoiceProviderError if consent is missing or no provider supports cloning.
        """
        if not request.consent_confirmed:
            raise VoiceProviderError(
                "Voice cloning requires explicit user authorization and consent verification."
            )

        candidates = self.find_compatible_providers(
            language="en",  # Base language check or general cloning support
            required_capability=VoiceCapability.VOICE_CLONING,
            preferred_provider=preferred_provider,
        )

        if not candidates:
            # Also check if any provider supports ZERO_SHOT_CLONING
            candidates = [
                p
                for p in self.providers
                if p.get_capabilities().supports(VoiceCapability.ZERO_SHOT_CLONING)
            ]

        if not candidates:
            raise VoiceProviderError("No registered voice provider supports voice cloning.")

        last_error = None
        for provider in candidates:
            try:
                logger.info(f"Routing voice cloning request to {provider.provider_name}")
                async with asyncio.timeout(self.request_timeout_seconds):
                    response = await provider.clone_voice(request)
                    logger.info(f"Voice cloning succeeded with provider {provider.provider_name}")
                    return response
            except TimeoutError:
                last_error = VoiceProviderError(
                    f"Voice cloning with {provider.provider_name} timed out"
                )
                logger.warning(f"Timeout on cloning with {provider.provider_name}")
            except Exception as e:
                last_error = e
                logger.warning(f"Cloning failed with {provider.provider_name}: {e}")

        raise VoiceProviderError(
            f"Voice cloning failed with all candidate providers. Last error: {last_error}"
        ) from last_error
