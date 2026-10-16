"""Microsoft Edge Neural TTS voice provider implementation.

Provides 100% free, high-fidelity Indian neural voices (Swara & Neerja)
with zero API keys, no subscription paywalls, and native Hindi/Hinglish/English support.
"""

import logging
import re
from typing import Any

try:
    import edge_tts
except ImportError:
    edge_tts = None

from app.services.voice.providers.base import (
    VoiceCloneRequest,
    VoiceCloneResponse,
    VoiceProvider,
    VoiceProviderError,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)
from app.services.voice.text_normalizer import clean_text_for_speech

logger = logging.getLogger(__name__)


class EdgeTTSProvider(VoiceProvider):
    """Microsoft Edge Neural TTS provider.

    Specialized for authentic Indian accents with natural pacing and emotion tuning.
    """

    DEFAULT_HINDI_VOICE = "hi-IN-SwaraNeural"
    DEFAULT_ENGLISH_VOICE = "en-IN-NeerjaNeural"
    EXPRESSIVE_ENGLISH_VOICE = "en-IN-NeerjaExpressiveNeural"

    # Emotion-driven rate and pitch adjustments (calibrated for stable vocal timbre)
    _EMOTION_SETTINGS: dict[str, dict[str, str]] = {
        "happy": {"rate": "-6%", "pitch": "+1Hz"},
        "excited": {"rate": "-5%", "pitch": "+1Hz"},
        "curious": {"rate": "-8%", "pitch": "+1Hz"},
        "playful": {"rate": "-6%", "pitch": "+1Hz"},
        "empathetic": {"rate": "-10%", "pitch": "-1Hz"},
        "serious": {"rate": "-10%", "pitch": "-1Hz"},
        "sad": {"rate": "-10%", "pitch": "-1Hz"},
        "warm": {"rate": "-8%", "pitch": "+0Hz"},
        "neutral": {"rate": "-8%", "pitch": "+0Hz"},
    }
    _DEFAULT_SETTINGS = {"rate": "-8%", "pitch": "+0Hz"}

    @property
    def provider_name(self) -> str:
        return "edge_tts"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        if edge_tts is None:
            raise VoiceProviderError(
                "edge_tts package is not installed. Install via: pip install edge-tts"
            )
        self.default_hindi_voice = config.get("hindi_voice", self.DEFAULT_HINDI_VOICE)
        self.default_english_voice = config.get("english_voice", self.DEFAULT_ENGLISH_VOICE)
        self.base_rate = config.get("rate", "-8%")
        logger.info("Initialized EdgeTTSProvider (Free Indian Neural Voices)")

    def get_capabilities(self):
        """Explicit capability declaration for Edge TTS provider."""
        from app.services.voice.providers.base import ProviderCapabilities, VoiceCapability

        return ProviderCapabilities(
            capabilities={
                VoiceCapability.TEXT_TO_SPEECH,
                VoiceCapability.EMOTION_CONTROL,
                VoiceCapability.SPEED_CONTROL,
                VoiceCapability.MULTI_LINGUAL,
            },
            supported_languages={
                "en",
                "hi",
                "hinglish",
                "ta",
                "te",
                "bn",
                "mr",
                "gu",
                "kn",
                "ml",
                "ur",
            },
            supported_audio_formats=["mp3", "wav"],
            sample_rates=[24000],
            is_commercial_ready=True,
            is_local_inference=False,
            license_type="Microsoft Online Services",
        )

    async def clone_voice(self, request: VoiceCloneRequest) -> VoiceCloneResponse:
        """Edge TTS is a neural preset provider; instant audio cloning is not supported."""
        raise VoiceProviderError(
            "Edge TTS does not support instant voice cloning from audio files. "
            "It provides free, studio-quality Indian neural voices: "
            f"'{self.DEFAULT_HINDI_VOICE}' (Hindi/Hinglish) and "
            f"'{self.DEFAULT_ENGLISH_VOICE}' (Indian English)."
        )

    async def synthesize_speech(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        """Synthesize speech using Microsoft Edge Neural TTS."""
        try:
            # ── Language & Script Detection ───────────────────────────────────
            has_devanagari = any("\u0900" <= ch <= "\u097f" for ch in request.text)
            hinglish_keywords = {
                "main",
                "mein",
                "tumahri",
                "aap",
                "kaise",
                "hai",
                "rhi",
                "hoon",
                "kr",
                "namaste",
                "shukriya",
                "kya",
                "theek",
                "baat",
                "bol",
                "kar",
                "rahi",
                "raha",
                "tum",
                "mera",
                "meri",
                "hum",
                "yaar",
                "bhai",
            }
            words = set(re.findall(r"\b[a-zA-Z]+\b", request.text.lower()))
            is_hindi = (
                has_devanagari
                or (request.language and request.language.lower().startswith("hi"))
                or bool(words & hinglish_keywords)
            )

            # ── Conversational Text Cleansing & Pronunciation Normalization ──
            # Strips markdown, emojis, code fences, and anchors "Raghvi" phonetics
            normalized_text = clean_text_for_speech(request.text, is_hindi=is_hindi)
            if not normalized_text.strip():
                normalized_text = "जी, समझ गई।" if is_hindi else "I understand."

            # ── Voice Selection & Persona Anchoring ───────────────────────────
            # If the caller requested an explicit Edge voice (e.g. Neerja), honor it.
            # If generic default or un-cloned UUID, anchor strictly to Swara (hi-IN-SwaraNeural).
            # Swara natively speaks both Hindi and English with authentic warmth, preventing
            # jarring turn-to-turn identity flips between two different people.
            # If explicit specialized provider voice (e.g. ElevenLabs ID), delegate to fallback.
            voice_id_str = (request.voice_id or "").strip()
            is_edge_voice = bool("-IN-" in voice_id_str or voice_id_str.endswith("Neural"))
            is_uuid = bool(
                re.match(
                    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
                    voice_id_str,
                )
            )
            is_generic_or_fallback = bool(
                not voice_id_str
                or voice_id_str in ["default", "none", "system", "auto"]
                or voice_id_str.startswith("aura-")
                or is_uuid
            )

            if not is_edge_voice and not is_generic_or_fallback:
                # Specific third-party provider voice ID (e.g. ElevenLabs custom clone)
                raise VoiceProviderError(
                    f"Voice ID '{voice_id_str}' is a specialized provider voice. "
                    "Delegating to next voice provider in fallback chain."
                )

            # Consistent persona: Swara serves as Raghvi's unified neural identity
            voice = voice_id_str if is_edge_voice else self.default_hindi_voice

            # ── Emotion & Pacing Settings ─────────────────────────────────────
            emotion_key = (request.emotion or "neutral").lower().strip()
            settings = self._EMOTION_SETTINGS.get(emotion_key, self._DEFAULT_SETTINGS)
            rate = settings["rate"]
            pitch = settings["pitch"]

            logger.info(
                f"EdgeTTS synthesizing: voice={voice}, emotion={emotion_key}, "
                f"rate={rate}, pitch={pitch}, text_len={len(normalized_text)}"
            )

            # ── Generate Speech ───────────────────────────────────────────────
            communicate = edge_tts.Communicate(
                text=normalized_text,
                voice=voice,
                rate=rate,
                pitch=pitch,
            )

            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]

            if not audio_data:
                raise VoiceProviderError("Edge TTS returned empty audio data")

            logger.info(f"EdgeTTS synthesized {len(audio_data)} bytes of audio")

            return VoiceSynthesisResponse(
                audio_data=audio_data,
                audio_format="mp3",
            )

        except Exception as e:
            logger.error(f"Edge TTS speech synthesis failed: {e}")
            raise VoiceProviderError(f"Edge TTS synthesis error: {e}") from e

    async def list_voices(self, language: str | None = None) -> list[dict[str, Any]]:
        """List available Indian neural voices."""
        voices = [
            {
                "voice_id": "hi-IN-SwaraNeural",
                "name": "Swara (Indian Hindi/Hinglish)",
                "gender": "Female",
                "locale": "hi-IN",
                "accent": "Indian",
                "description": "Natural, warm conversational Indian Hindi & Hinglish voice",
            },
            {
                "voice_id": "en-IN-NeerjaNeural",
                "name": "Neerja (Indian English)",
                "gender": "Female",
                "locale": "en-IN",
                "accent": "Indian",
                "description": "Polite, friendly Indian English female voice",
            },
            {
                "voice_id": "en-IN-NeerjaExpressiveNeural",
                "name": "Neerja Expressive (Indian English)",
                "gender": "Female",
                "locale": "en-IN",
                "accent": "Indian",
                "description": "Dynamic, expressive Indian English female voice",
            },
            {
                "voice_id": "hi-IN-MadhurNeural",
                "name": "Madhur (Indian Hindi)",
                "gender": "Male",
                "locale": "hi-IN",
                "accent": "Indian",
                "description": "Clear Indian Hindi male voice",
            },
            {
                "voice_id": "en-IN-PrabhatNeural",
                "name": "Prabhat (Indian English)",
                "gender": "Male",
                "locale": "en-IN",
                "accent": "Indian",
                "description": "Conversational Indian English male voice",
            },
        ]
        if language:
            return [v for v in voices if v["locale"].startswith(language)]
        return voices

    async def delete_voice(self, voice_id: str) -> bool:
        """Preset neural voices cannot be deleted."""
        return False

    async def get_voice_info(self, voice_id: str) -> dict[str, Any]:
        """Get voice information."""
        voices = await self.list_voices()
        for v in voices:
            if v["voice_id"] == voice_id:
                return v
        return {"voice_id": voice_id, "provider": "edge_tts"}
