"""Deepgram voice provider implementation (TTS)."""

import logging
from typing import Any

import aiohttp

from app.services.voice.providers.base import (
    VoiceProvider,
    VoiceProviderError,
    VoiceCloneRequest,
    VoiceCloneResponse,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)

logger = logging.getLogger(__name__)


class DeepgramProvider(VoiceProvider):
    """Deepgram TTS provider."""

    BASE_URL = "https://api.deepgram.com/v1"

    @property
    def provider_name(self) -> str:
        return "deepgram"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "aura-asteria-en")

        if not self.api_key:
            logger.warning("Deepgram API key not configured")

    async def clone_voice(self, request: VoiceCloneRequest) -> VoiceCloneResponse:
        """Voice cloning not supported by Deepgram."""
        raise VoiceProviderError(
            "Voice cloning not supported by Deepgram. Use preset voices."
        )

    async def synthesize_speech(
        self, request: VoiceSynthesisRequest
    ) -> VoiceSynthesisResponse:
        """Synthesize speech using Deepgram TTS."""

        if not self.api_key:
            raise VoiceProviderError("Deepgram API key not configured")

        try:
            # Use voice_id as the model/voice name
            model = request.voice_id if request.voice_id.startswith("aura-") else self.model

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/speak",
                    headers={
                        "Authorization": f"Token {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    params={"model": model, "encoding": "linear16", "sample_rate": 44100},
                    json={"text": request.text},
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise VoiceProviderError(
                            f"Deepgram synthesis error: {response.status} - {error_text}"
                        )

                    audio_data = await response.read()

                    logger.info(
                        f"Speech synthesized with Deepgram: {len(audio_data)} bytes"
                    )

                    return VoiceSynthesisResponse(
                        audio_data=audio_data,
                        audio_format="wav",
                    )

        except Exception as e:
            logger.error(f"Deepgram speech synthesis failed: {e}")
            raise VoiceProviderError(f"Failed to synthesize speech: {e}") from e

    async def list_voices(self, language: str | None = None) -> list[dict[str, Any]]:
        """List available Deepgram voices."""
        # Deepgram Aura voices (as of 2024)
        voices = [
            {"id": "aura-asteria-en", "name": "Asteria", "language": "en"},
            {"id": "aura-luna-en", "name": "Luna", "language": "en"},
            {"id": "aura-stella-en", "name": "Stella", "language": "en"},
            {"id": "aura-athena-en", "name": "Athena", "language": "en"},
            {"id": "aura-hera-en", "name": "Hera", "language": "en"},
            {"id": "aura-orion-en", "name": "Orion", "language": "en"},
            {"id": "aura-arcas-en", "name": "Arcas", "language": "en"},
            {"id": "aura-perseus-en", "name": "Perseus", "language": "en"},
            {"id": "aura-angus-en", "name": "Angus", "language": "en"},
            {"id": "aura-orpheus-en", "name": "Orpheus", "language": "en"},
        ]

        if language:
            voices = [v for v in voices if v["language"] == language]

        return voices

    async def delete_voice(self, voice_id: str) -> bool:
        """Delete voice (not applicable for preset voices)."""
        return True

    async def get_voice_info(self, voice_id: str) -> dict[str, Any]:
        """Get voice information."""
        voices = await self.list_voices()
        for voice in voices:
            if voice["id"] == voice_id:
                return voice

        return {"voice_id": voice_id, "provider": "deepgram"}
