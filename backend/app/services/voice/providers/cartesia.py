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
        model_id = config.get("model_id", "sonic")
        if model_id in ["sonic-multilingual", "sonic-english"]:
            model_id = "sonic"
        self.model_id = model_id

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

    # ─── Emotion → Cartesia experimental_controls mapping ─────────────────────
    # Each entry is a list of emotion strings Cartesia's __experimental_controls
    # accepts. Composite tags (e.g. "positivity:high") give more intensity.
    _EMOTION_MAP: dict[str, list[str]] = {
        "happy": ["positivity:high"],
        "excited": ["positivity:high", "surprise:high"],
        "joyful": ["positivity:high"],
        "curious": ["curiosity:high"],
        "playful": ["positivity:moderate", "curiosity:moderate"],
        "warm": ["positivity:moderate"],
        "empathetic": ["sadness:low"],  # slight softness, not full sadness
        "sad": ["sadness:high"],
        "depressed": ["sadness:high"],
        "angry": ["anger:high"],
        "frustrated": ["anger:moderate"],
        "serious": [],  # no emotion tag = flat/neutral
        "neutral": [],
    }

    # Emotion → speech rate (1.0 = normal)
    _EMOTION_SPEED: dict[str, float] = {
        "happy": 1.05,
        "excited": 1.12,
        "playful": 1.08,
        "curious": 1.00,
        "warm": 0.97,
        "empathetic": 0.90,
        "sad": 0.88,
        "depressed": 0.85,
        "serious": 0.95,
        "frustrated": 1.03,
        "angry": 1.05,
        "neutral": 1.00,
    }

    async def synthesize_speech(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        """Synthesize speech using Cartesia with emotion-driven settings."""

        if not self.api_key:
            raise VoiceProviderError("Cartesia API key not configured")

        try:
            import re

            emotion_key = (request.emotion or "neutral").lower().strip()

            # ── Voice ID validation ───────────────────────────────────────────
            is_uuid = bool(
                re.match(
                    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
                    request.voice_id,
                )
            )
            # Default Cartesia voice ID (Helpful Woman — Sonic)
            voice_id = request.voice_id if is_uuid else "a0e99841-438c-4a64-b679-ae501e7d6091"

            # ── Emotion → Cartesia controls ───────────────────────────────────
            cartesia_emotions = self._EMOTION_MAP.get(emotion_key, [])
            voice_config: dict = {"mode": "id", "id": voice_id}
            if cartesia_emotions:
                voice_config["__experimental_controls"] = {"emotion": cartesia_emotions}

            # ── Language detection ────────────────────────────────────────────
            has_devanagari = any("\u0900" <= ch <= "\u097f" for ch in request.text)
            language = "hi" if has_devanagari else (request.language or "en")

            # ── Speed variation by emotion ────────────────────────────────────
            speed = self._EMOTION_SPEED.get(emotion_key, 1.0)

            payload = {
                "model_id": self.model_id,
                "transcript": request.text,
                "language": language,
                "voice": voice_config,
                "output_format": {
                    "container": "wav",
                    "encoding": "pcm_f32le",
                    "sample_rate": 44100,
                },
            }
            # Only add speed if non-default to keep payload minimal
            if speed != 1.0:
                payload["speed"] = speed

            logger.info(
                f"Cartesia TTS: voice={voice_id}, emotion={emotion_key}, "
                f"lang={language}, speed={speed}, "
                f"cartesia_emotions={cartesia_emotions}"
            )

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

                logger.info(f"Cartesia speech synthesized: {len(audio_data)} bytes")

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
