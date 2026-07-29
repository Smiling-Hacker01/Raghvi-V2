"""Tests for voice provider fallback adapter."""

import pytest

from app.services.voice.fallback_adapter import VoiceProviderFallbackAdapter
from app.services.voice.providers.base import (
    VoiceProviderError,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)


class MockSuccessProvider:
    """Mock provider that always succeeds."""

    provider_name = "mock_success"

    async def synthesize_speech(
        self, request: VoiceSynthesisRequest
    ) -> VoiceSynthesisResponse:
        return VoiceSynthesisResponse(
            audio_data=b"mock audio data", audio_format="wav"
        )


class MockFailProvider:
    """Mock provider that always fails."""

    provider_name = "mock_fail"

    async def synthesize_speech(
        self, request: VoiceSynthesisRequest
    ) -> VoiceSynthesisResponse:
        raise VoiceProviderError("Mock provider failure")


@pytest.mark.asyncio
async def test_fallback_first_provider_succeeds():
    """Test that first provider is used when it succeeds."""

    # Create adapter and manually set providers to bypass initialization
    adapter = VoiceProviderFallbackAdapter.__new__(VoiceProviderFallbackAdapter)
    adapter.provider_configs = []
    adapter.providers = [MockSuccessProvider(), MockSuccessProvider()]

    request = VoiceSynthesisRequest(text="Hello", voice_id="test", language="en")

    response = await adapter.synthesize_speech(request)

    assert response.audio_data == b"mock audio data"
    assert response.audio_format == "wav"


@pytest.mark.asyncio
async def test_fallback_to_second_provider():
    """Test that second provider is used when first fails."""

    adapter = VoiceProviderFallbackAdapter.__new__(VoiceProviderFallbackAdapter)
    adapter.provider_configs = []
    adapter.providers = [MockFailProvider(), MockSuccessProvider()]

    request = VoiceSynthesisRequest(text="Hello", voice_id="test", language="en")

    response = await adapter.synthesize_speech(request)

    assert response.audio_data == b"mock audio data"
    assert response.audio_format == "wav"


@pytest.mark.asyncio
async def test_all_providers_fail():
    """Test that error is raised when all providers fail."""

    adapter = VoiceProviderFallbackAdapter.__new__(VoiceProviderFallbackAdapter)
    adapter.provider_configs = []
    adapter.providers = [MockFailProvider(), MockFailProvider()]

    request = VoiceSynthesisRequest(text="Hello", voice_id="test", language="en")

    with pytest.raises(VoiceProviderError) as exc_info:
        await adapter.synthesize_speech(request)

    assert "All voice providers failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fallback_order():
    """Test that providers are tried in order."""

    call_order = []

    class OrderedMockProvider:
        def __init__(self, name: str, should_fail: bool):
            self.provider_name = name
            self.should_fail = should_fail

        async def synthesize_speech(
            self, request: VoiceSynthesisRequest
        ) -> VoiceSynthesisResponse:
            call_order.append(self.provider_name)

            if self.should_fail:
                raise VoiceProviderError(f"{self.provider_name} failed")

            return VoiceSynthesisResponse(audio_data=b"success", audio_format="wav")

    adapter = VoiceProviderFallbackAdapter.__new__(VoiceProviderFallbackAdapter)
    adapter.provider_configs = []
    adapter.providers = [
        OrderedMockProvider("provider1", should_fail=True),
        OrderedMockProvider("provider2", should_fail=True),
        OrderedMockProvider("provider3", should_fail=False),
    ]

    request = VoiceSynthesisRequest(text="Hello", voice_id="test", language="en")

    response = await adapter.synthesize_speech(request)

    assert call_order == ["provider1", "provider2", "provider3"]
    assert response.audio_data == b"success"


@pytest.mark.asyncio
async def test_provider_status():
    """Test provider status reporting."""

    adapter = VoiceProviderFallbackAdapter.__new__(VoiceProviderFallbackAdapter)
    adapter.provider_configs = []
    adapter.providers = [MockSuccessProvider(), MockFailProvider()]

    status = adapter.get_provider_status()

    assert len(status) == 2
    assert "mock_success" in status
    assert "mock_fail" in status
    assert status["mock_success"]["priority"] == 1
    assert status["mock_fail"]["priority"] == 2


def test_empty_providers_initialization():
    """Test that adapter requires at least one provider."""

    with pytest.raises(ValueError) as exc_info:
        VoiceProviderFallbackAdapter([])

    assert "No voice providers" in str(exc_info.value)
