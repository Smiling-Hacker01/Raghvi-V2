"""Cartesia AI voice provider implementation."""

import logging
from typing import Any

import aiofiles
import aiohttp

from app.services.voice.providers.base import (
    VoiceCloneRequest,
    VoiceCloneResponse,
    VoiceProvider,
    VoiceProviderError,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)

logger = logging.getLogger(__name__)


class CartesiaProvider(VoiceProvider):
    """Cartesia AI real-time voice synthesis provider."""

    BASE_URL = "https://api.cartesia.ai"

    @property
    def provider_name(self) -> str:
        return "cartesia"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.model_id = config.get("model_id", "sonic-multilingual")

        if not self.api_key:
            logger.warning("Cartesia API key not configured")

    async def clone_voice(self, request: VoiceCloneRequest) -> VoiceCloneResponse:
        """Clone voice (Cartesia supports voice cloning)."""

        if not self.api_key:
            raise VoiceProviderError("Cartesia API key not configured")

        try:
            # Read audio file
            async with aiofiles.open(request.audio_file_path, "rb") as f:
                audio_data = await f.read()

            # Cartesia voice cloning API
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    f"{self.BASE_URL}/voices/embed",
                    headers={
                        "X-API-Key": self.api_key,
                        "Content-Type": "application/octet-stream",
                    },
                    data=audio_data,
                ) as response,
            ):
                if response.status != 200:
                    error_text = await response.text()
                    raise VoiceProviderError(
                        f"Cartesia API error: {response.status} - {error_text}"
                    )

                result = await response.json()
                embedding = result.get("embedding")

                if not embedding:
                    raise VoiceProviderError("No embedding returned from Cartesia")

                # Store embedding as voice_id
                voice_id = f"cartesia_embedding_{request.user_id}_{request.voice_name}"

                logger.info(f"Voice cloned successfully with Cartesia: {voice_id}")

                return VoiceCloneResponse(
                    voice_id=voice_id,
                    voice_name=request.voice_name,
                    provider=self.provider_name,
                )

        except Exception as e:
            logger.error(f"Cartesia voice cloning failed: {e}")
            raise VoiceProviderError(f"Failed to clone voice: {e}") from e

    async def synthesize_speech(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        """Synthesize speech using Cartesia."""

        if not self.api_key:
            raise VoiceProviderError("Cartesia API key not configured")

        try:
            # Map LLM emotion to Cartesia's supported emotions
            cartesia_emotion = None
            if request.emotion:
                emotion_map = {
                    "happy": "positivity",
                    "excited": "positivity",
                    "joyful": "positivity",
                    "sad": "sadness",
                    "sadness": "sadness",
                    "depressed": "sadness",
                    "angry": "anger",
                    "anger": "anger",
                    "frustrated": "anger",
                    "surprise": "surprise",
                    "curious": "surprise",
                    "shocked": "surprise",
                }
                # Find best match or default to None
                mapped = emotion_map.get(request.emotion.lower())
                if mapped:
                    cartesia_emotion = [mapped]

            voice_config = {
                "mode": "id",
                "id": request.voice_id,
            }

            if cartesia_emotion:
                voice_config["__experimental_controls"] = {"emotion": cartesia_emotion}

            payload = {
                "model_id": self.model_id,
                "transcript": request.text,
                "voice": voice_config,
                "output_format": {
                    "container": "wav",
                    "encoding": "pcm_f32le",
                    "sample_rate": 44100,
                },
            }

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    f"{self.BASE_URL}/tts/bytes",
                    headers={
                        "X-API-Key": self.api_key,
                        "Cartesia-Version": "2024-06-10",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response,
            ):
                if response.status != 200:
                    error_text = await response.text()
                    raise VoiceProviderError(
                        f"Cartesia synthesis error: {response.status} - {error_text}"
                    )

                audio_data = await response.read()

                logger.info(f"Speech synthesized with Cartesia: {len(audio_data)} bytes")

                return VoiceSynthesisResponse(
                    audio_data=audio_data,
                    audio_format="wav",
                )

        except Exception as e:
            logger.error(f"Cartesia speech synthesis failed: {e}")
            raise VoiceProviderError(f"Failed to synthesize speech: {e}") from e

    async def list_voices(self, language: str | None = None) -> list[dict[str, Any]]:
        """List available voices."""

        if not self.api_key:
            raise VoiceProviderError("Cartesia API key not configured")

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    f"{self.BASE_URL}/voices",
                    headers={"X-API-Key": self.api_key},
                ) as response,
            ):
                if response.status != 200:
                    error_text = await response.text()
                    raise VoiceProviderError(
                        f"Cartesia API error: {response.status} - {error_text}"
                    )

                result = await response.json()
                voices = result.get("voices", [])

                return voices

        except Exception as e:
            logger.error(f"Failed to list Cartesia voices: {e}")
            raise VoiceProviderError(f"Failed to list voices: {e}") from e

    async def delete_voice(self, voice_id: str) -> bool:
        """Delete voice (embeddings are stored locally, no deletion needed)."""
        logger.info(f"Cartesia voice deletion requested: {voice_id}")
        return True

    async def get_voice_info(self, voice_id: str) -> dict[str, Any]:
        """Get voice information."""
        return {
            "voice_id": voice_id,
            "provider": "cartesia",
            "note": "Voice embeddings are stored locally",
        }
