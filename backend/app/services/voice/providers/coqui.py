"""Coqui TTS voice provider implementation (local/offline)."""

import logging
from typing import Any

from app.services.voice.providers.base import (
    VoiceCloneRequest,
    VoiceCloneResponse,
    VoiceProvider,
    VoiceProviderError,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)

logger = logging.getLogger(__name__)


class CoquiProvider(VoiceProvider):
    """Coqui TTS provider for local voice synthesis."""

    @property
    def provider_name(self) -> str:
        return "coqui"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.model_name = config.get("model_name", "tts_models/en/ljspeech/tacotron2-DDC")
        self.tts = None

        # Note: TTS model loading is deferred until first use
        logger.info(f"Coqui provider initialized with model: {self.model_name}")

    def _load_model(self):
        """Load TTS model (lazy loading)."""
        if self.tts is None:
            try:
                from TTS.api import TTS

                self.tts = TTS(self.model_name)
                logger.info("Coqui TTS model loaded")
            except ImportError as e:
                raise VoiceProviderError("Coqui TTS not installed. Install with: pip install TTS") from e
            except Exception as e:
                raise VoiceProviderError(f"Failed to load TTS model: {e}") from e

    async def clone_voice(self, request: VoiceCloneRequest) -> VoiceCloneResponse:
        """Clone voice (not supported by basic Coqui TTS)."""
        raise VoiceProviderError(
            "Voice cloning not supported by basic Coqui TTS. "
            "Use YourTTS or XTTS models for voice cloning."
        )

    async def synthesize_speech(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        """Synthesize speech using Coqui TTS."""

        try:
            self._load_model()

            # Synthesize to file (TTS library requirement)
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                output_path = tmp_file.name

            self.tts.tts_to_file(
                text=request.text,
                file_path=output_path,
            )

            # Read audio data
            with open(output_path, "rb") as f:
                audio_data = f.read()

            # Clean up
            import os

            os.unlink(output_path)

            logger.info(f"Speech synthesized: {len(audio_data)} bytes")

            return VoiceSynthesisResponse(
                audio_data=audio_data,
                audio_format="wav",
            )

        except Exception as e:
            logger.error(f"Speech synthesis failed: {e}")
            raise VoiceProviderError(f"Failed to synthesize speech: {e}") from e

    async def list_voices(self, language: str | None = None) -> list[dict[str, Any]]:
        """List available voices (returns empty for basic Coqui)."""
        return []

    async def delete_voice(self, voice_id: str) -> bool:
        """Delete voice (not supported)."""
        return False

    async def get_voice_info(self, voice_id: str) -> dict[str, Any]:
        """Get voice info (not supported)."""
        return {}
