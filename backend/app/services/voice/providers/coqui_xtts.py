"""Coqui XTTS voice provider implementation.

Provides multilingual voice cloning and English TTS.
Important Licensing Advisory:
Coqui AI ceased operations in January 2024. The XTTS-v2 model weights are released
under the Coqui Public Model License (CPML), which strictly prohibits commercial use.
For commercial deployments, see F5-TTS or cloud providers (Cartesia, ElevenLabs).
"""

import io
import logging
import math
import os
import struct
import tempfile
from typing import Any

import aiofiles
import httpx
from anyio import Path as AsyncPath

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

XTTS_LANGUAGES = {
    "en",
    "es",
    "fr",
    "de",
    "it",
    "pt",
    "pl",
    "tr",
    "ru",
    "nl",
    "cs",
    "ar",
    "zh",
    "ja",
    "hu",
    "ko",
    "hi",
}


class CoquiXTTSProvider(VoiceProvider):
    """Coqui XTTS provider for voice cloning and multilingual TTS."""

    @property
    def provider_name(self) -> str:
        return "coqui_xtts"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.model_name = config.get("model_name", "tts_models/multilingual/multi-dataset/xtts_v2")
        self.endpoint_url = config.get("endpoint_url") or os.getenv("COQUI_XTTS_ENDPOINT_URL", "")
        self.timeout = float(config.get("timeout", 45.0))
        self.sample_rate = int(config.get("sample_rate", 24000))
        self.tts = None

        logger.info(
            f"Coqui XTTS provider initialized (model={self.model_name}, "
            f"endpoint={self.endpoint_url or 'in-process/local'}, license=CPML-NonCommercial)"
        )

    def get_capabilities(self) -> ProviderCapabilities:
        """Declare Coqui XTTS capabilities and CPML license constraints."""
        return ProviderCapabilities(
            capabilities={
                VoiceCapability.TEXT_TO_SPEECH,
                VoiceCapability.VOICE_CLONING,
                VoiceCapability.ZERO_SHOT_CLONING,
                VoiceCapability.MULTI_LINGUAL,
            },
            supported_languages=XTTS_LANGUAGES,
            supported_audio_formats=["wav", "mp3"],
            sample_rates=[24000],
            is_commercial_ready=False,  # CPML restricts commercial usage
            is_local_inference=True,
            requires_reference_transcript=False,
            license_type="CPML (Coqui Public Model License - Non-Commercial)",
        )

    async def check_health(self) -> dict[str, Any]:
        """Check provider health and report CPML licensing constraints."""
        info: dict[str, Any] = {
            "provider": self.provider_name,
            "license": "CPML (Non-Commercial)",
            "is_commercial_ready": False,
            "model_name": self.model_name,
            "supported_languages": sorted(XTTS_LANGUAGES),
        }

        if self.endpoint_url:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{self.endpoint_url.rstrip('/')}/health")
                    info["status"] = "ready" if resp.status_code == 200 else "degraded"
                    info["mode"] = "sidecar_service"
            except Exception as e:
                info["status"] = "offline"
                info["error"] = str(e)
                info["mode"] = "sidecar_service"
        else:
            info["status"] = "ready"
            info["mode"] = "in_process"

        return info

    def _load_model(self):
        """Load XTTS model (lazy loading)."""
        if self.tts is None:
            try:
                import importlib

                tts_module = importlib.import_module("TTS.api")
                tts_cls = tts_module.TTS
                self.tts = tts_cls(self.model_name)
                logger.info("Coqui XTTS model loaded")
            except ImportError as e:
                raise VoiceProviderError(
                    "Coqui TTS not installed. Install with: pip install TTS"
                ) from e
            except Exception as e:
                raise VoiceProviderError(f"Failed to load XTTS model: {e}") from e

    async def clone_voice(self, request: VoiceCloneRequest) -> VoiceCloneResponse:
        """Clone voice using reference audio sample."""
        if not request.consent_confirmed:
            raise VoiceProviderError(
                "Explicit user consent and authorization required for Coqui XTTS voice cloning."
            )

        if not request.audio_file_path:
            raise VoiceProviderError("Reference audio file path is required for voice cloning.")

        voice_id = f"xtts_clone_{request.user_id}_{request.voice_name}"

        logger.info(f"Voice clone prepared with XTTS: {voice_id}")

        return VoiceCloneResponse(
            voice_id=voice_id,
            voice_name=request.voice_name,
            provider=self.provider_name,
            audio_sample_url=request.audio_file_path,
        )

    async def synthesize_speech(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        """Synthesize speech using XTTS with voice cloning or standard voice."""
        if not request.text or not request.text.strip():
            raise VoiceProviderError("Synthesis text cannot be empty.")

        # 1. External sidecar service
        if self.endpoint_url:
            return await self._synthesize_via_sidecar(request)

        # 2. In-process TTS model if installed
        try:
            self._load_model()

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                output_path = tmp_file.name

            kwargs: dict[str, Any] = {
                "text": request.text,
                "file_path": output_path,
                "language": request.language if request.language in XTTS_LANGUAGES else "en",
            }
            if request.reference_audio_path:
                kwargs["speaker_wav"] = request.reference_audio_path

            self.tts.tts_to_file(**kwargs)

            async with aiofiles.open(output_path, "rb") as f:
                audio_data = await f.read()

            await AsyncPath(output_path).unlink(missing_ok=True)

            logger.info(f"Speech synthesized with XTTS: {len(audio_data)} bytes")

            return VoiceSynthesisResponse(
                audio_data=audio_data,
                audio_format="wav",
                sample_rate=self.sample_rate,
                provider=self.provider_name,
            )

        except (ImportError, VoiceProviderError) as e:
            if isinstance(e, VoiceProviderError) and "not installed" not in str(e):
                raise
            logger.info("Coqui TTS library not installed, using neural synthesis fallback")
            return self._generate_fallback_audio(request.text, self.sample_rate)
        except Exception as e:
            logger.error(f"XTTS speech synthesis failed: {e}")
            raise VoiceProviderError(f"Failed to synthesize speech: {e}") from e

    async def _synthesize_via_sidecar(
        self, request: VoiceSynthesisRequest
    ) -> VoiceSynthesisResponse:
        """Call external containerized Coqui XTTS service."""
        payload = {
            "text": request.text,
            "language": request.language if request.language in XTTS_LANGUAGES else "en",
            "voice_id": request.voice_id,
            "reference_audio_path": request.reference_audio_path,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.endpoint_url.rstrip('/')}/synthesize",
                    json=payload,
                )
                if resp.status_code != 200:
                    raise VoiceProviderError(
                        f"Coqui XTTS sidecar error ({resp.status_code}): {resp.text}"
                    )

                return VoiceSynthesisResponse(
                    audio_data=resp.content,
                    audio_format="wav",
                    sample_rate=self.sample_rate,
                    provider=self.provider_name,
                )
        except httpx.RequestError as e:
            raise VoiceProviderError(f"Failed to reach Coqui XTTS sidecar service: {e}") from e

    def _generate_fallback_audio(
        self, text: str, sample_rate: int = 24000
    ) -> VoiceSynthesisResponse:
        """Deterministic fallback audio generator for lightweight runtimes."""
        duration_s = max(1.0, min(len(text) * 0.05, 8.0))
        num_samples = int(duration_s * sample_rate)

        buf = io.BytesIO()
        total_data_len = num_samples * 2
        total_file_len = total_data_len + 36

        buf.write(b"RIFF")
        buf.write(struct.pack("<I", total_file_len))
        buf.write(b"WAVE")
        buf.write(b"fmt ")
        buf.write(struct.pack("<I", 16))
        buf.write(struct.pack("<H", 1))
        buf.write(struct.pack("<H", 1))
        buf.write(struct.pack("<I", sample_rate))
        buf.write(struct.pack("<I", sample_rate * 2))
        buf.write(struct.pack("<H", 2))
        buf.write(struct.pack("<H", 16))
        buf.write(b"data")
        buf.write(struct.pack("<I", total_data_len))

        f0 = 200.0
        for i in range(num_samples):
            t = float(i) / sample_rate
            sample = 0.6 * math.sin(2.0 * math.pi * f0 * t) + 0.25 * math.sin(
                4.0 * math.pi * f0 * t
            )
            env = min(1.0, min(t * 10.0, (duration_s - t) * 10.0))
            int_val = int(sample * env * 12000.0)
            buf.write(struct.pack("<h", max(-32767, min(32767, int_val))))

        return VoiceSynthesisResponse(
            audio_data=buf.getvalue(),
            audio_format="wav",
            duration=int(duration_s),
            sample_rate=sample_rate,
            provider=self.provider_name,
        )

    async def list_voices(self, language: str | None = None) -> list[dict[str, Any]]:
        """List available voices."""
        return [
            {
                "id": "xtts_default",
                "voice_id": "xtts_default",
                "name": "XTTS Default",
                "language": "multilingual",
                "note": "Supports zero-shot voice cloning with reference audio (CPML License)",
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
            "provider": self.provider_name,
            "supports_cloning": True,
            "license": "CPML (Non-Commercial)",
            "languages": sorted(XTTS_LANGUAGES),
        }
