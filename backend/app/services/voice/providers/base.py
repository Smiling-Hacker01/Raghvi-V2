"""Base voice provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class VoiceCloneRequest:
    """Request to clone a voice."""

    user_id: str
    voice_name: str
    audio_file_path: str
    audio_format: str = "wav"
    sample_rate: int = 44100


@dataclass
class VoiceSynthesisRequest:
    """Request to synthesize speech."""

    text: str
    voice_id: str
    language: str = "en"
    output_format: str = "wav"


@dataclass
class VoiceCloneResponse:
    """Response from voice cloning."""

    voice_id: str
    voice_name: str
    provider: str
    audio_sample_url: str | None = None
    audio_sample_duration: int | None = None


@dataclass
class VoiceSynthesisResponse:
    """Response from voice synthesis."""

    audio_data: bytes
    audio_format: str
    duration: int | None = None


class VoiceProviderError(Exception):
    """Base exception for voice provider errors."""

    pass


class VoiceProvider(ABC):
    """Abstract base class for voice providers."""

    def __init__(self, config: dict[str, Any]):
        """Initialize provider with configuration."""
        self.config = config

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get provider name."""
        pass

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
