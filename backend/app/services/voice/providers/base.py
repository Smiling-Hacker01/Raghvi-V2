"""Base voice provider interface and vendor-agnostic capability contracts."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class VoiceCapability(StrEnum):
    """Capabilities supported by a voice provider."""

    TEXT_TO_SPEECH = "tts"
    VOICE_CLONING = "voice_cloning"
    ZERO_SHOT_CLONING = "zero_shot_cloning"
    STREAMING = "streaming"
    EMOTION_CONTROL = "emotion_control"
    MULTI_LINGUAL = "multi_lingual"
    SPEED_CONTROL = "speed_control"


@dataclass
class ProviderCapabilities:
    """Explicit capability declaration for a voice provider."""

    capabilities: set[VoiceCapability] = field(default_factory=set)
    supported_languages: set[str] = field(default_factory=set)
    supported_audio_formats: list[str] = field(default_factory=lambda: ["wav", "mp3"])
    sample_rates: list[int] = field(default_factory=lambda: [24000, 44100])
    is_commercial_ready: bool = True
    is_local_inference: bool = False
    requires_reference_transcript: bool = False
    license_type: str = "Permissive"

    def supports(self, capability: VoiceCapability) -> bool:
        """Check if provider supports a given capability."""
        return capability in self.capabilities

    def supports_language(self, language: str) -> bool:
        """Check if provider supports a specific language code."""
        lang_code = language.lower().split("-")[0].strip()
        return lang_code in self.supported_languages or "*" in self.supported_languages


@dataclass
class VoiceCloneRequest:
    """Request to clone a voice."""

    user_id: str
    voice_name: str
    audio_file_path: str
    audio_format: str = "wav"
    sample_rate: int = 44100
    reference_text: str | None = None
    consent_confirmed: bool = True


@dataclass
class VoiceSynthesisRequest:
    """Request to synthesize speech."""

    text: str
    voice_id: str
    language: str = "en"
    emotion: str | None = None
    output_format: str = "wav"
    reference_audio_path: str | None = None
    reference_text: str | None = None
    speed: float | None = 1.0


@dataclass
class VoiceCloneResponse:
    """Response from voice cloning."""

    voice_id: str
    voice_name: str
    provider: str
    audio_sample_url: str | None = None
    audio_sample_duration: int | None = None
    reference_text: str | None = None


@dataclass
class VoiceSynthesisResponse:
    """Response from voice synthesis."""

    audio_data: bytes
    audio_format: str
    duration: int | None = None
    sample_rate: int = 24000
    provider: str | None = None


class VoiceProviderError(Exception):
    """Base exception for voice provider errors."""

    pass


class VoiceProvider(ABC):
    """Abstract base class for vendor-agnostic voice providers."""

    def __init__(self, config: dict[str, Any]):
        """Initialize provider with configuration."""
        self.config = config

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get provider name."""
        pass

    def get_capabilities(self) -> ProviderCapabilities:
        """Get provider capabilities. Providers can override with specific capabilities."""
        return ProviderCapabilities(
            capabilities={VoiceCapability.TEXT_TO_SPEECH},
            supported_languages={"en"},
            supported_audio_formats=["wav", "mp3"],
            sample_rates=[24000, 44100],
        )

    async def check_health(self) -> dict[str, Any]:
        """Check provider readiness and connectivity."""
        caps = self.get_capabilities()
        return {
            "status": "ready",
            "provider": self.provider_name,
            "is_commercial_ready": caps.is_commercial_ready,
            "license_type": caps.license_type,
            "capabilities": [c.value for c in caps.capabilities],
            "supported_languages": sorted(caps.supported_languages),
        }

    @abstractmethod
    async def clone_voice(self, request: VoiceCloneRequest) -> VoiceCloneResponse:
        """Clone a voice from audio sample."""
        pass

    @abstractmethod
    async def synthesize_speech(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        """Synthesize speech from text using a voice."""
        pass

    @abstractmethod
    async def list_voices(self, language: str | None = None) -> list[dict[str, Any]]:
        """List available voices."""
        pass

    @abstractmethod
    async def delete_voice(self, voice_id: str) -> bool:
        """Delete a cloned voice."""
        pass

    @abstractmethod
    async def get_voice_info(self, voice_id: str) -> dict[str, Any]:
        """Get voice information."""
        pass
