"""Tests for voice adapter builder."""

from unittest.mock import patch

from app.core.config import Settings
from app.services.voice.voice_adapter_builder import (
    build_voice_adapter,
    get_voice_adapter,
    reset_voice_adapter,
)


def test_build_voice_adapter_default_priority():
    reset_voice_adapter()
    mock_settings = Settings(
        voice_provider_priority="",
        elevenlabs_api_key="",
        cartesia_api_key="",
        deepgram_api_key="",
        nvidia_api_key="",
    )

    with patch("app.services.voice.voice_adapter_builder.get_settings", return_value=mock_settings):
        adapter = build_voice_adapter()
        # Should fallback to local coqui_xtts
        assert adapter is not None
        assert len(adapter.providers) > 0

    reset_voice_adapter()


def test_build_voice_adapter_configured_providers():
    reset_voice_adapter()
    mock_settings = Settings(
        voice_provider_priority="elevenlabs,cartesia,deepgram,nvidia,coqui,coqui_xtts,unknown",
        elevenlabs_api_key="key1",
        cartesia_api_key="key2",
        deepgram_api_key="key3",
        nvidia_api_key="key4",
    )

    with patch("app.services.voice.voice_adapter_builder.get_settings", return_value=mock_settings):
        adapter = build_voice_adapter()
        assert len(adapter.providers) == 6

    reset_voice_adapter()


def test_get_voice_adapter_singleton():
    reset_voice_adapter()
    adapter1 = get_voice_adapter()
    adapter2 = get_voice_adapter()
    assert adapter1 is adapter2
    reset_voice_adapter()
