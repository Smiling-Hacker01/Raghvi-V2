"""Tests for vendor-agnostic voice architecture (IndicF5, Coqui, Router)."""

import os
import tempfile
from unittest.mock import patch

import pytest
from httpx import AsyncClient, Response

from app.services.voice.provider_factory import VoiceProviderFactory
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
from app.services.voice.providers.coqui_xtts import CoquiXTTSProvider
from app.services.voice.providers.indicf5 import IndicF5Provider
from app.services.voice.router import VoiceRouter

# ── Fixtures and Test Helpers ───────────────────────────────────────────────────


class DummyMockProvider(VoiceProvider):
    """Test helper provider."""

    def __init__(
        self,
        name: str,
        languages: set[str],
        caps: set[VoiceCapability],
        should_fail: bool = False,
    ):
        super().__init__({})
        self._name = name
        self._languages = languages
        self._caps = caps
        self.should_fail = should_fail
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return self._name

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            capabilities=self._caps,
            supported_languages=self._languages,
            supported_audio_formats=["wav", "mp3"],
            sample_rates=[24000],
            is_commercial_ready=True,
            license_type="MIT",
        )

    async def check_health(self) -> dict:
        return {"status": "ready", "provider": self._name}

    async def synthesize_speech(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        self.call_count += 1
        if self.should_fail:
            raise VoiceProviderError(f"{self._name} synthetic failure")
        return VoiceSynthesisResponse(
            audio_data=f"audio_from_{self._name}".encode(),
            audio_format="wav",
            sample_rate=24000,
            provider=self._name,
        )

    async def clone_voice(self, request: VoiceCloneRequest) -> VoiceCloneResponse:
        self.call_count += 1
        if self.should_fail:
            raise VoiceProviderError(f"{self._name} cloning failure")
        return VoiceCloneResponse(
            voice_id=f"{self._name}_voice_123",
            voice_name=request.voice_name,
            provider=self._name,
            reference_text=request.reference_text,
        )

    async def list_voices(self, language: str | None = None) -> list[dict]:
        return []

    async def get_voice_info(self, voice_id: str) -> dict:
        return {"voice_id": voice_id, "provider": self._name}

    async def delete_voice(self, voice_id: str) -> bool:
        return True


@pytest.fixture
def temp_sample_wav():
    """Create a temporary real WAV audio file for cloning tests."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        # Create minimal 44-byte valid WAV header
        header = bytearray(44)
        header[0:4] = b"RIFF"
        header[8:12] = b"WAVE"
        header[12:16] = b"fmt "
        header[16:20] = (16).to_bytes(4, "little")  # subchunk size
        header[20:22] = (1).to_bytes(2, "little")  # PCM
        header[22:24] = (1).to_bytes(2, "little")  # Mono
        header[24:28] = (24000).to_bytes(4, "little")  # sample rate
        header[28:32] = (48000).to_bytes(4, "little")  # byte rate
        header[32:34] = (2).to_bytes(2, "little")  # block align
        header[34:36] = (16).to_bytes(2, "little")  # bits per sample
        header[36:40] = b"data"
        # 1 second of dummy PCM samples
        pcm = b"\x00\x00" * 24000
        header[40:44] = len(pcm).to_bytes(4, "little")
        header[4:8] = (len(pcm) + 36).to_bytes(4, "little")
        f.write(header + pcm)
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)


# ── Phase 2: Provider Contract & Capabilities Tests ─────────────────────────────


def test_voice_capability_enum_and_contract():
    """Verify explicit capabilities contract."""
    caps = ProviderCapabilities(
        capabilities={VoiceCapability.TEXT_TO_SPEECH, VoiceCapability.ZERO_SHOT_CLONING},
        supported_languages={"hi", "en"},
    )
    assert caps.supports(VoiceCapability.TEXT_TO_SPEECH) is True
    assert caps.supports(VoiceCapability.STREAMING) is False
    assert caps.supports_language("hi") is True
    assert caps.supports_language("hi-IN") is True
    assert caps.supports_language("fr") is False


def test_provider_factory_registration_and_discovery():
    """Test dynamic provider factory registration and error handling."""
    providers = VoiceProviderFactory.list_providers()
    assert "indicf5" in providers
    assert "coqui_xtts" in providers
    assert "edge_tts" in providers

    with pytest.raises(VoiceProviderError) as exc_info:
        VoiceProviderFactory.create_provider("unregistered_provider", {})
    assert "Unknown voice provider" in str(exc_info.value)


# ── Phase 3A: IndicF5 Provider Tests ───────────────────────────────────────────


def test_indicf5_capabilities_declaration():
    """Verify IndicF5 declares verified Indian languages and MIT license."""
    provider = IndicF5Provider({"endpoint_url": "http://localhost:8008"})
    caps = provider.get_capabilities()

    assert caps.supports(VoiceCapability.TEXT_TO_SPEECH) is True
    assert caps.supports(VoiceCapability.ZERO_SHOT_CLONING) is True
    assert caps.is_commercial_ready is True
    assert caps.license_type == "MIT"

    # Verify 11 official Indian languages
    for lang in ["hi", "ta", "te", "bn", "mr", "gu", "kn", "ml", "pa", "or", "as", "hinglish"]:
        assert caps.supports_language(lang) is True, f"IndicF5 must support {lang}"


def test_indicf5_input_validation():
    """Test text length and language validation."""
    provider = IndicF5Provider({})

    # Empty text
    with pytest.raises(VoiceProviderError) as exc_info:
        provider._validate_synthesis_input("", "hi")
    assert "cannot be empty" in str(exc_info.value)

    # Exceeds max length
    with pytest.raises(VoiceProviderError) as exc_info:
        provider._validate_synthesis_input("A" * 600, "hi")
    assert "exceeds maximum allowed length" in str(exc_info.value)

    # Unsupported language
    with pytest.raises(VoiceProviderError) as exc_info:
        provider._validate_synthesis_input("Bonjour", "fr")
    assert "Language 'fr' is not supported by IndicF5" in str(exc_info.value)


@pytest.mark.asyncio
async def test_indicf5_health_check():
    """Test IndicF5 health check in both sidecar and in-process modes."""
    # Sidecar mode with mock endpoint
    provider = IndicF5Provider({"endpoint_url": "http://mock-indicf5:8000"})
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Response(200, json={"status": "ok", "model": "IndicF5"})
        health = await provider.check_health()
        assert health["status"] == "ready"
        assert health["mode"] == "sidecar_service"

    # In-process mode
    local_provider = IndicF5Provider({"endpoint_url": ""})
    health_local = await local_provider.check_health()
    assert health_local["status"] == "ready"
    assert health_local["mode"] in ("in_process", "in_process_fallback")


@pytest.mark.asyncio
async def test_indicf5_sidecar_synthesis(temp_sample_wav):
    """Test IndicF5 HTTP sidecar synthesis."""
    provider = IndicF5Provider({"endpoint_url": "http://mock-indicf5:8000"})
    dummy_wav_bytes = b"RIFFmockwavdata"

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = Response(200, content=dummy_wav_bytes)
        request = VoiceSynthesisRequest(
            text="नमस्ते, आप कैसे हैं?",
            voice_id="indic_swara",
            language="hi",
            reference_audio_path=temp_sample_wav,
            reference_text="नमस्ते",
        )
        response = await provider.synthesize_speech(request)
        assert response.audio_data == dummy_wav_bytes
        assert response.sample_rate == 24000
        assert response.provider == "indicf5"


@pytest.mark.asyncio
async def test_indicf5_zero_shot_voice_cloning(temp_sample_wav):
    """Test IndicF5 zero-shot voice cloning enrollment."""
    provider = IndicF5Provider({"endpoint_url": "http://mock-indicf5:8000"})

    request = VoiceCloneRequest(
        user_id="user_123",
        voice_name="My Voice",
        audio_file_path=temp_sample_wav,
        reference_text="यह मेरी आवाज़ का नमूना है",
        consent_confirmed=True,
    )

    clone_resp = await provider.clone_voice(request)
    assert clone_resp.voice_id.startswith("indicf5_clone_user_123_")
    assert clone_resp.reference_text == "यह मेरी आवाज़ का नमूना है"
    assert clone_resp.provider == "indicf5"


# ── Phase 3B: Coqui XTTS Provider Tests ─────────────────────────────────────────


def test_coqui_xtts_capabilities_and_cpml_license():
    """Verify Coqui XTTS flags CPML non-commercial restriction."""
    provider = CoquiXTTSProvider({"endpoint_url": "http://localhost:8020"})
    caps = provider.get_capabilities()

    assert caps.supports(VoiceCapability.TEXT_TO_SPEECH) is True
    assert caps.supports(VoiceCapability.VOICE_CLONING) is True
    assert caps.is_commercial_ready is False  # Must be False due to CPML
    assert "CPML" in caps.license_type
    assert caps.supports_language("en") is True


@pytest.mark.asyncio
async def test_coqui_xtts_sidecar_synthesis(temp_sample_wav):
    """Test Coqui XTTS sidecar synthesis flow."""
    provider = CoquiXTTSProvider({"endpoint_url": "http://mock-coqui:8020"})
    dummy_wav = b"RIFFcoquiaudiodata"

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = Response(200, content=dummy_wav)
        request = VoiceSynthesisRequest(
            text="Hello world, testing Coqui voice cloning.",
            voice_id="coqui_default",
            language="en",
            reference_audio_path=temp_sample_wav,
        )
        response = await provider.synthesize_speech(request)
        assert response.audio_data == dummy_wav
        assert response.provider == "coqui_xtts"


@pytest.mark.asyncio
async def test_coqui_xtts_health_check():
    """Test Coqui XTTS health check exposes CPML licensing details."""
    provider = CoquiXTTSProvider({})
    health = await provider.check_health()
    assert health["provider"] == "coqui_xtts"
    assert health["is_commercial_ready"] is False
    assert "CPML" in health["license"]


# ── Phase 3C & 4: Voice Router Routing and Failover Tests ───────────────────────


def test_voice_router_language_specialization():
    """Test router routes Indic languages to IndicF5 and English to Coqui/Edge."""
    p_indic = DummyMockProvider("indicf5", {"hi", "ta", "te"}, {VoiceCapability.TEXT_TO_SPEECH})
    p_coqui = DummyMockProvider("coqui_xtts", {"en"}, {VoiceCapability.TEXT_TO_SPEECH})
    p_edge = DummyMockProvider("edge_tts", {"en", "hi"}, {VoiceCapability.TEXT_TO_SPEECH})

    router = VoiceRouter([p_edge, p_coqui, p_indic])

    # Routing Hindi -> indicf5 must rank first
    hindi_candidates = router.find_compatible_providers("hi", VoiceCapability.TEXT_TO_SPEECH)
    assert [p.provider_name for p in hindi_candidates] == ["indicf5", "edge_tts"]

    # Routing English -> coqui_xtts ranks above general edge_tts
    english_candidates = router.find_compatible_providers("en", VoiceCapability.TEXT_TO_SPEECH)
    assert english_candidates[0].provider_name == "coqui_xtts"


def test_voice_router_preferred_provider_override():
    """Explicit user preference overrides default ranking."""
    p_indic = DummyMockProvider("indicf5", {"hi"}, {VoiceCapability.TEXT_TO_SPEECH})
    p_edge = DummyMockProvider("edge_tts", {"hi"}, {VoiceCapability.TEXT_TO_SPEECH})

    router = VoiceRouter([p_indic, p_edge])
    candidates = router.find_compatible_providers("hi", preferred_provider="edge_tts")
    assert candidates[0].provider_name == "edge_tts"


@pytest.mark.asyncio
async def test_voice_router_failover_mechanism():
    """Verify automatic failover when primary provider fails."""
    primary_fail = DummyMockProvider(
        "primary_fail", {"en"}, {VoiceCapability.TEXT_TO_SPEECH}, should_fail=True
    )
    secondary_ok = DummyMockProvider(
        "secondary_ok", {"en"}, {VoiceCapability.TEXT_TO_SPEECH}, should_fail=False
    )

    router = VoiceRouter([primary_fail, secondary_ok])
    request = VoiceSynthesisRequest(text="Hello failover test", voice_id="v1", language="en")

    response = await router.synthesize_speech(request)
    assert response.provider == "secondary_ok"
    assert primary_fail.call_count == 1
    assert secondary_ok.call_count == 1


@pytest.mark.asyncio
async def test_voice_router_unsupported_language_rejection():
    """Unsupported language raises clear error and refuses silent substitution."""
    p_indic = DummyMockProvider("indicf5", {"hi"}, {VoiceCapability.TEXT_TO_SPEECH})
    router = VoiceRouter([p_indic])

    request = VoiceSynthesisRequest(text="Bonjour", voice_id="v1", language="fr")
    with pytest.raises(VoiceProviderError) as exc_info:
        await router.synthesize_speech(request)
    assert "No voice provider supports TTS for language 'fr'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_voice_router_cloning_requires_consent():
    """Voice cloning without explicit user consent is rejected immediately."""
    p_cloner = DummyMockProvider("cloner", {"*"}, {VoiceCapability.VOICE_CLONING})
    router = VoiceRouter([p_cloner])

    request = VoiceCloneRequest(
        user_id="user_1",
        voice_name="Cloned",
        audio_file_path="/tmp/fake.wav",
        consent_confirmed=False,  # No consent
    )

    with pytest.raises(VoiceProviderError) as exc_info:
        await router.clone_voice(request)
    assert "Voice cloning requires explicit user authorization" in str(exc_info.value)


@pytest.mark.asyncio
async def test_voice_router_health_checks_aggregation():
    """Test router aggregates health check results across providers."""
    p1 = DummyMockProvider("prov1", {"en"}, {VoiceCapability.TEXT_TO_SPEECH})
    p2 = DummyMockProvider("prov2", {"hi"}, {VoiceCapability.TEXT_TO_SPEECH})

    router = VoiceRouter([p1, p2])
    health = await router.check_health_all()

    assert "prov1" in health
    assert "prov2" in health
    assert health["prov1"]["status"] == "ready"


# ── Phase 5: Voice API Integration Tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_providers_capabilities_endpoint(client: AsyncClient, auth_headers: dict):
    """Test GET /voices/providers/capabilities returns detailed provider metadata."""
    response = await client.get("/voices/providers/capabilities", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "providers" in data
    assert "total_providers" in data


@pytest.mark.asyncio
async def test_api_providers_health_endpoint(client: AsyncClient, auth_headers: dict):
    """Test GET /voices/providers/health returns readiness status."""
    response = await client.get("/voices/providers/health", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "providers" in data
    assert "timestamp" in data


def test_indicf5_script_detection_and_aliases():
    """Verify script detection across Indian languages and script ranges."""
    provider = IndicF5Provider({})

    # Aliases
    assert provider.normalize_language("hindi") == "hi"
    assert provider.normalize_language("tamil") == "ta"
    assert provider.normalize_language("telugu") == "te"
    assert provider.normalize_language("bengali") == "bn"
    assert provider.normalize_language("gujarati") == "gu"
    assert provider.normalize_language("kannada") == "kn"
    assert provider.normalize_language("malayalam") == "ml"
    assert provider.normalize_language("marathi") == "mr"
    assert provider.normalize_language("odia") == "or"
    assert provider.normalize_language("punjabi") == "pa"
    assert provider.normalize_language("assamese") == "as"

    # Script detection
    assert provider.detect_script_or_language("வணக்கம்") == "ta"
    assert provider.detect_script_or_language("నమస్కారం") == "te"
    assert provider.detect_script_or_language("নমস্কার") == "bn"
    assert provider.detect_script_or_language("નમસ્તે") == "gu"
    assert provider.detect_script_or_language("\u0ca8\u0cae\u0cb8\u0ccd\u0c95\u0cbe\u0cb0") == "kn"
    assert provider.detect_script_or_language("നമസ്കാരം") == "ml"
    assert provider.detect_script_or_language("ਨਮਸਤੇ") == "pa"
    assert provider.detect_script_or_language("ନମସ୍କାର") == "or"
    assert provider.detect_script_or_language("नमस्ते") == "hi"
    assert provider.detect_script_or_language("Hello there", fallback_language="en") == "en"


@pytest.mark.asyncio
async def test_indicf5_fallback_audio_and_voices():
    """Test IndicF5 deterministic audio synthesis fallback and voice catalog."""
    provider = IndicF5Provider({})

    # Audio synthesis fallback
    audio_resp = provider._generate_fallback_audio("नमस्ते भारत")
    assert len(audio_resp.audio_data) > 44
    assert audio_resp.audio_data.startswith(b"RIFF")
    assert audio_resp.audio_format == "wav"

    # List voices
    all_voices = await provider.list_voices()
    assert len(all_voices) >= 11
    hi_voices = await provider.list_voices(language="hi")
    assert len(hi_voices) == 1
    assert hi_voices[0]["language"] == "hi"

    # Delete voice
    assert await provider.delete_voice("indicf5_dummy_voice") is True


@pytest.mark.asyncio
async def test_indicf5_local_fallback_synthesis(temp_sample_wav):
    """Test in-process synthesis invokes fallback when PyTorch is not loaded."""
    provider = IndicF5Provider({"endpoint_url": ""})
    req = VoiceSynthesisRequest(
        text="नमस्ते राघवी",
        voice_id="indicf5_default",
        language="hi",
        reference_audio_path=temp_sample_wav,
    )
    resp = await provider.synthesize_speech(req)
    assert resp.audio_data.startswith(b"RIFF")
    assert resp.provider == "indicf5"


@pytest.mark.asyncio
async def test_coqui_xtts_voices_and_fallback():
    """Test Coqui XTTS voice listing, info, fallback audio, and deletion."""
    provider = CoquiXTTSProvider({})

    # Voices listing
    voices = await provider.list_voices()
    assert len(voices) > 0
    en_voices = await provider.list_voices("en")
    assert len(en_voices) > 0

    # Voice info
    info = await provider.get_voice_info(voices[0]["voice_id"])
    assert info["provider"] == "coqui_xtts"

    # Fallback audio
    fallback = provider._generate_fallback_audio("Testing Coqui fallback audio generator")
    assert fallback.audio_data.startswith(b"RIFF")
    assert fallback.sample_rate == 24000

    # Delete voice
    assert await provider.delete_voice(voices[0]["voice_id"]) is True


@pytest.mark.asyncio
async def test_router_get_provider_and_registration():
    """Test VoiceRouter provider registration, lookup, and zero-shot cloning routing."""
    p_cloner = DummyMockProvider("cloner_zero_shot", {"hi"}, {VoiceCapability.ZERO_SHOT_CLONING})
    router = VoiceRouter()
    router.register_provider(p_cloner)

    assert router.get_provider("cloner_zero_shot") is p_cloner
    assert router.get_provider("nonexistent") is None

    # Clone routing with zero-shot capability
    req = VoiceCloneRequest(
        user_id="user_test",
        voice_name="ZeroShot",
        audio_file_path="/tmp/audio.wav",
        consent_confirmed=True,
    )
    res = await router.clone_voice(req)
    assert res.voice_id == "cloner_zero_shot_voice_123"


@pytest.mark.asyncio
async def test_fallback_adapter_router_integration():
    """Test VoiceProviderFallbackAdapter router delegation and capabilities."""
    from app.services.voice.fallback_adapter import VoiceProviderFallbackAdapter

    adapter = VoiceProviderFallbackAdapter.__new__(VoiceProviderFallbackAdapter)
    adapter.provider_configs = []
    p1 = DummyMockProvider("prov_a", {"en"}, {VoiceCapability.TEXT_TO_SPEECH})
    p2 = DummyMockProvider("prov_b", {"hi"}, {VoiceCapability.TEXT_TO_SPEECH})
    adapter.providers = [p1, p2]

    # Router delegation
    router = adapter.get_router()
    assert router is not None
    assert len(router.providers) == 2

    caps = adapter.get_capabilities_map()
    assert "prov_a" in caps
    assert "prov_b" in caps

    health = await adapter.check_health_all()
    assert health["prov_a"]["status"] == "ready"
    assert health["prov_b"]["status"] == "ready"
