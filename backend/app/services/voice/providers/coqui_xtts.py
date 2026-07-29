"""Coqui XTTS voice provider implementation (advanced voice cloning)."""

import logging
from typing import Any

from app.services.voice.providers.base import (
    VoiceProvider,
    VoiceProviderError,
    VoiceCloneRequest,
    VoiceCloneResponse,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)

logger = logging.getLogger(__name__)


class CoquiXTTSProvider(VoiceProvider):
    """Coqui XTTS provider for voice cloning and multilingual TTS."""

    @property
    def provider_name(self) -> str:
        return "coqui_xtts"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.model_name = config.get("model_name", "tts_models/multilingual/multi-dataset/xtts_v2")
        self.tts = None

        logger.info(f"Coqui XTTS provider initialized with model: {self.model_name}")

    def _load_model(self):
        """Load XTTS model (lazy loading)."""
        if self.tts is None:
            try:
                from TTS.api import TTS

                self.tts = TTS(self.model_name)
                logger.info("Coqui XTTS model loaded")
            except ImportError as e:
                raise VoiceProviderError(
                    "Coqui TTS not installed. Install with: pip install TTS"
                ) from e
            except Exception as e:
                raise VoiceProviderError(f"Failed to load XTTS model: {e}") from e

    async def clone_voice(self, request: VoiceCloneRequest) -> VoiceCloneResponse:
        """Clone voice using XTTS."""

        try:
            self._load_model()

            # XTTS uses reference audio directly for cloning
            # Store the audio path as the voice_id
            voice_id = f"xtts_clone_{request.user_id}_{request.voice_name}"

            logger.info(f"Voice clone prepared with XTTS: {voice_id}")

            return VoiceCloneResponse(
                voice_id=voice_id,
                voice_name=request.voice_name,
                provider=self.provider_name,
                audio_sample_url=request.audio_file_path,
            )

        except Exception as e:
            logger.error(f"XTTS voice cloning failed: {e}")
            raise VoiceProviderError(f"Failed to clone voice: {e}") from e

    async def synthesize_speech(
        self, request: VoiceSynthesisRequest
    ) -> VoiceSynthesisResponse:
        """Synthesize speech using XTTS with voice cloning."""

        try:
            self._load_model()

            # XTTS requires reference audio for voice cloning
            # In production, retrieve the audio file path from voice_id
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                output_path = tmp_file.name

            # Synthesize with speaker reference
            # Note: In production, you'd get the speaker_wav from the voice record
            self.tts.tts_to_file(
                text=request.text,
                file_path=output_path,
                language=request.language,
                # speaker_wav="path/to/reference.wav",  # Add this for cloning
            )

            # Read audio data
            with open(output_path, "rb") as f:
                audio_data = f.read()

            # Clean up
            import os

            os.unlink(output_path)

            logger.info(f"Speech synthesized with XTTS: {len(audio_data)} bytes")

            return VoiceSynthesisResponse(
                audio_data=audio_data,
                audio_format="wav",
            )

        except Exception as e:
            logger.error(f"XTTS speech synthesis failed: {e}")
            raise VoiceProviderError(f"Failed to synthesize speech: {e}") from e

    async def list_voices(self, language: str | None = None) -> list[dict[str, Any]]:
        """List available voices (XTTS uses voice cloning)."""
        return [
            {
                "id": "xtts_default",
                "name": "XTTS Default",
                "language": "multilingual",
                "note": "Supports voice cloning with reference audio",
            }
        ]

    async def delete_voice(self, voice_id: str) -> bool:
        """Delete voice."""
        logger.info(f"XTTS voice deletion: {voice_id}")
        return True

    async def get_voice_info(self, voice_id: str) -> dict[str, Any]:
        """Get voice information."""
        return {
            "voice_id": voice_id,
            "provider": "coqui_xtts",
            "supports_cloning": True,
            "languages": ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko", "hi"],
        }
