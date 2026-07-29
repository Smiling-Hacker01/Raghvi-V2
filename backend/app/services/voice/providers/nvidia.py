"""NVIDIA NeMo voice provider implementation."""

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


class NvidiaProvider(VoiceProvider):
    """NVIDIA NeMo TTS provider."""

    BASE_URL = "https://api.nvidia.com/v1"

    @property
    def provider_name(self) -> str:
        return "nvidia"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "fastpitch")

        if not self.api_key:
            logger.warning("NVIDIA API key not configured")

    async def clone_voice(self, request: VoiceCloneRequest) -> VoiceCloneResponse:
        """Voice cloning with NVIDIA NeMo (requires custom model)."""
        raise VoiceProviderError(
            "Voice cloning requires custom NVIDIA NeMo model deployment. "
            "Use pretrained voices or deploy custom model."
        )

    async def synthesize_speech(
        self, request: VoiceSynthesisRequest
    ) -> VoiceSynthesisResponse:
        """Synthesize speech using NVIDIA NeMo."""

        if not self.api_key:
            raise VoiceProviderError("NVIDIA API key not configured")

        try:
            payload = {
                "text": request.text,
                "voice": request.voice_id,
                "language": request.language,
                "sample_rate": 44100,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/audio/generations",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise VoiceProviderError(
                            f"NVIDIA synthesis error: {response.status} - {error_text}"
                        )

                    audio_data = await response.read()

                    logger.info(
                        f"Speech synthesized with NVIDIA: {len(audio_data)} bytes"
                    )

                    return VoiceSynthesisResponse(
                        audio_data=audio_data,
                        audio_format="wav",
                    )

        except Exception as e:
            logger.error(f"NVIDIA speech synthesis failed: {e}")
            raise VoiceProviderError(f"Failed to synthesize speech: {e}") from e

    async def list_voices(self, language: str | None = None) -> list[dict[str, Any]]:
        """List available NVIDIA voices."""
        # Example voices (actual API may differ)
        voices = [
            {"id": "nvidia_en_us_female_1", "name": "Female US 1", "language": "en"},
            {"id": "nvidia_en_us_male_1", "name": "Male US 1", "language": "en"},
            {"id": "nvidia_en_uk_female_1", "name": "Female UK 1", "language": "en"},
        ]

        if language:
            voices = [v for v in voices if v["language"] == language]

        return voices

    async def delete_voice(self, voice_id: str) -> bool:
        """Delete voice."""
        return True

    async def get_voice_info(self, voice_id: str) -> dict[str, Any]:
        """Get voice information."""
        return {"voice_id": voice_id, "provider": "nvidia"}
