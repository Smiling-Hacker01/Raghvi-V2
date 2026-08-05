"""ElevenLabs voice provider implementation."""

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


class ElevenLabsProvider(VoiceProvider):
    """ElevenLabs voice cloning and synthesis provider."""

    BASE_URL = "https://api.elevenlabs.io/v1"

    @property
    def provider_name(self) -> str:
        return "elevenlabs"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        model_id = config.get("model_id", "eleven_multilingual_v2")
        # Upgrade deprecated models automatically
        if model_id in ["eleven_monolingual_v1", "eleven_multilingual_v1"]:
            model_id = "eleven_multilingual_v2"
        self.model_id = model_id

        if not self.api_key:
            logger.warning("ElevenLabs API key not configured")

    async def clone_voice(self, request: VoiceCloneRequest) -> VoiceCloneResponse:
        """Clone a voice using ElevenLabs API."""

        if not self.api_key:
            raise VoiceProviderError("ElevenLabs API key not configured")

        try:
            # Read audio file
            async with aiofiles.open(request.audio_file_path, "rb") as f:
                audio_data = await f.read()

            # Prepare multipart form data
            form_data = aiohttp.FormData()
            form_data.add_field("name", request.voice_name)
            form_data.add_field(
                "files",
                audio_data,
                filename=f"{request.voice_name}.{request.audio_format}",
                content_type=f"audio/{request.audio_format}",
            )

            # Call ElevenLabs API
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    f"{self.BASE_URL}/voices/add",
                    headers={"xi-api-key": self.api_key},
                    data=form_data,
                ) as response,
            ):
                if response.status != 200:
                    error_text = await response.text()
                    raise VoiceProviderError(
                        f"ElevenLabs API error: {response.status} - {error_text}"
                    )

                result = await response.json()
                voice_id = result.get("voice_id")

                if not voice_id:
                    raise VoiceProviderError("No voice_id returned from ElevenLabs")

                logger.info(f"Voice cloned successfully: {voice_id}")

                return VoiceCloneResponse(
                    voice_id=voice_id,
                    voice_name=request.voice_name,
                    provider=self.provider_name,
                )

        except Exception as e:
            logger.error(f"Voice cloning failed: {e}")
            raise VoiceProviderError(f"Failed to clone voice: {e}") from e

    # Emotion → voice settings mapping.
    # stability:       lower = more expressive/varied, higher = consistent/flat
    # style:           0–1 exaggeration of voice style (ElevenLabs v2+ only)
    # similarity_boost: how closely to match the cloned voice timbre
    _EMOTION_VOICE_SETTINGS: dict[str, dict] = {
        "happy": {"stability": 0.35, "similarity_boost": 0.75, "style": 0.42},
        "excited": {"stability": 0.28, "similarity_boost": 0.75, "style": 0.55},
        "curious": {"stability": 0.38, "similarity_boost": 0.75, "style": 0.35},
        "playful": {"stability": 0.30, "similarity_boost": 0.75, "style": 0.50},
        "empathetic": {"stability": 0.50, "similarity_boost": 0.80, "style": 0.22},
        "serious": {"stability": 0.58, "similarity_boost": 0.80, "style": 0.15},
        "sad": {"stability": 0.52, "similarity_boost": 0.80, "style": 0.18},
        "warm": {"stability": 0.42, "similarity_boost": 0.78, "style": 0.30},
        "neutral": {"stability": 0.40, "similarity_boost": 0.75, "style": 0.28},
    }
    _DEFAULT_VOICE_SETTINGS = {"stability": 0.40, "similarity_boost": 0.75, "style": 0.30}

    async def synthesize_speech(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        """Synthesize speech using ElevenLabs API with emotion-driven voice settings."""

        if not self.api_key:
            raise VoiceProviderError("ElevenLabs API key not configured")

        try:
            import re

            # ── Language detection ────────────────────────────────────────────
            # Detect Devanagari (Hindi) script — triggers multilingual phonemes
            has_devanagari = any("\u0900" <= ch <= "\u097f" for ch in request.text)
            language_code = "hi" if has_devanagari else "en"

            # ── Emotion-driven voice settings ─────────────────────────────────
            emotion_key = (request.emotion or "neutral").lower().strip()
            voice_settings = self._EMOTION_VOICE_SETTINGS.get(
                emotion_key, self._DEFAULT_VOICE_SETTINGS
            )

            payload = {
                "text": request.text,
                "model_id": self.model_id,
                "language_code": language_code,
                "voice_settings": {
                    **voice_settings,
                    "use_speaker_boost": True,  # adds warmth and vocal presence
                },
            }

            # ── Voice ID validation ───────────────────────────────────────────
            # If a UUID or Deepgram-style voice_id was passed, fall back to
            # the free-tier ElevenLabs demo voice (Sarah)
            is_uuid = bool(
                re.match(
                    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
                    request.voice_id,
                )
            )
            voice_id = (
                "EXAVITQu4vr4xnSDxMaL"
                if (is_uuid or request.voice_id.startswith("aura-"))
                else request.voice_id
            )

            logger.info(
                f"ElevenLabs TTS: voice={voice_id}, emotion={emotion_key}, "
                f"lang={language_code}, model={self.model_id}, "
                f"stability={voice_settings['stability']}"
            )

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    f"{self.BASE_URL}/text-to-speech/{voice_id}",
                    headers={
                        "xi-api-key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response,
            ):
                if response.status != 200:
                    error_text = await response.text()
                    raise VoiceProviderError(
                        f"ElevenLabs synthesis error: {response.status} - {error_text}"
                    )

                audio_data = await response.read()

                logger.info(f"ElevenLabs speech synthesized: {len(audio_data)} bytes")

                return VoiceSynthesisResponse(
                    audio_data=audio_data,
                    audio_format=request.output_format,
                )

        except Exception as e:
            logger.error(f"ElevenLabs speech synthesis failed: {e}")
            raise VoiceProviderError(f"Failed to synthesize speech: {e}") from e

    async def list_voices(self, language: str | None = None) -> list[dict[str, Any]]:
        """List available voices."""

        if not self.api_key:
            raise VoiceProviderError("ElevenLabs API key not configured")

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    f"{self.BASE_URL}/voices",
                    headers={"xi-api-key": self.api_key},
                ) as response,
            ):
                if response.status != 200:
                    error_text = await response.text()
                    raise VoiceProviderError(
                        f"ElevenLabs API error: {response.status} - {error_text}"
                    )

                result = await response.json()
                voices = result.get("voices", [])

                return voices

        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            raise VoiceProviderError(f"Failed to list voices: {e}") from e

    async def delete_voice(self, voice_id: str) -> bool:
        """Delete a cloned voice."""

        if not self.api_key:
            raise VoiceProviderError("ElevenLabs API key not configured")

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.delete(
                    f"{self.BASE_URL}/voices/{voice_id}",
                    headers={"xi-api-key": self.api_key},
                ) as response,
            ):
                if response.status == 200:
                    logger.info(f"Voice deleted: {voice_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to delete voice: {error_text}")
                    return False

        except Exception as e:
            logger.error(f"Failed to delete voice: {e}")
            return False

    async def get_voice_info(self, voice_id: str) -> dict[str, Any]:
        """Get voice information."""

        if not self.api_key:
            raise VoiceProviderError("ElevenLabs API key not configured")

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    f"{self.BASE_URL}/voices/{voice_id}",
                    headers={"xi-api-key": self.api_key},
                ) as response,
            ):
                if response.status != 200:
                    error_text = await response.text()
                    raise VoiceProviderError(
                        f"ElevenLabs API error: {response.status} - {error_text}"
                    )

                return await response.json()

        except Exception as e:
            logger.error(f"Failed to get voice info: {e}")
            raise VoiceProviderError(f"Failed to get voice info: {e}") from e
