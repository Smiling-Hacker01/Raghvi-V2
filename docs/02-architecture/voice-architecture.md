# Voice Architecture — Vendor-Agnostic Voice AI Infrastructure

## 1. Overview

Raghvi V2's voice subsystem provides a **vendor-agnostic, plugin-based voice AI architecture** with support for:
1. **Multi-provider Speech Synthesis (TTS)** with capability-aware routing and automatic failover.
2. **Polyglot Indian-Language Synthesis** powered by **IndicF5** (AI4Bharat) covering 11 official Indian languages and Hinglish.
3. **Zero-Shot Voice Cloning** with mandatory explicit user consent, reference-audio transcription alignment, and full lifecycle data management.
4. **Coqui XTTS Integration** for high-fidelity English and multilingual synthesis with strict **CPML (Coqui Public Model License) non-commercial guardrails**.
5. **Subscription-Gated Quotas & S3 Storage** with encrypted sample isolation.

The architecture decouples conversational business logic from underlying voice models, allowing seamless hot-swapping, sidecar scaling, and addition of new providers without altering core application services.

---

## 2. Core Architecture & Components

```
                    ┌────────────────────────────┐
                    │ Conversational Application │
                    │ (/chat/send-with-voice, UI)│
                    └─────────────┬──────────────┘
                                  │
                                  ▼
                    ┌────────────────────────────┐
                    │        VoiceService        │
                    │ (Consent, Quotas, Storage) │
                    └─────────────┬──────────────┘
                                  │
                                  ▼
                    ┌────────────────────────────┐
                    │        VoiceRouter         │
                    │(Language & Capability Map) │
                    └──────┬───────────────┬─────┘
                           │               │
            ┌──────────────┴───┐       ┌───┴──────────────┐
            │  Indian Language │       │ English / Global │
            │      Routing     │       │     Routing      │
            └──────────┬───────┘       └───┬──────────────┘
                       │                   │
                       ▼                   ▼
            ┌──────────────────┐       ┌──────────────────┐
            │  IndicF5Provider │       │ CoquiXTTSProvider│
            │(11 Langs, 24kHz) │       │ (CPML Guardrail) │
            └──────────┬───────┘       └───┬──────────────┘
                       │                   │
        ┌──────────────┴───────┐   ┌───────┴──────────────┐
        │ Sidecar / Local PyTorch   │ Cloud Failover Chains│
        │ (ai4bharat/IndicF5)       │ (EdgeTTS, ElevenLabs)│
        └──────────────────────┘   └──────────────────────┘
```

### 2.1 The Shared Provider Contract (`VoiceProvider`)

Every voice provider adheres to the abstract contract defined in `backend/app/services/voice/providers/base.py`:

```python
class VoiceProvider(ABC):
    """Abstract base class for all vendor-agnostic voice providers."""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier (e.g., 'indicf5', 'coqui_xtts', 'edge_tts')."""
        pass

    def get_capabilities(self) -> ProviderCapabilities:
        """Explicit capability declaration."""
        ...

    async def check_health(self) -> dict[str, Any]:
        """Readiness and connectivity status check."""
        ...

    @abstractmethod
    async def synthesize_speech(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        """Synthesize text into PCM/WAV/MP3 audio."""
        pass

    @abstractmethod
    async def clone_voice(self, request: VoiceCloneRequest) -> VoiceCloneResponse:
        """Enroll or clone a voice from reference audio."""
        pass
```

### 2.2 Capability Discovery Contract (`ProviderCapabilities`)

Providers explicitly declare their verified capabilities rather than relying on assumed features:

```python
class VoiceCapability(StrEnum):
    TEXT_TO_SPEECH = "tts"
    VOICE_CLONING = "voice_cloning"
    ZERO_SHOT_CLONING = "zero_shot_cloning"
    STREAMING = "streaming"
    EMOTION_CONTROL = "emotion_control"
    MULTI_LINGUAL = "multi_lingual"
    SPEED_CONTROL = "speed_control"

@dataclass
class ProviderCapabilities:
    capabilities: set[VoiceCapability]
    supported_languages: set[str]
    supported_audio_formats: list[str] = field(default_factory=lambda: ["wav", "mp3"])
    sample_rates: list[int] = field(default_factory=lambda: [24000, 44100])
    is_commercial_ready: bool = True
    is_local_inference: bool = False
    requires_reference_transcript: bool = False
    license_type: str = "Permissive"
```

---

## 3. Technology Evaluation: IndicF5 & Coqui XTTS

| Metric | IndicF5 (AI4Bharat) | Coqui XTTS-v2 | Edge Neural TTS | ElevenLabs |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Domain** | Indian Languages & Hinglish | English & Multilingual | Indian English & Hindi | Global English & Clones |
| **Supported Indian Languages** | **11** (`hi, ta, te, bn, mr, gu, kn, ml, pa, or, as`) + `hinglish` | Hindi (limited) | `hi, en-IN, ta, te, bn, mr, gu, kn, ml, ur` | Multilingual (29+) |
| **Zero-Shot Voice Cloning** | Supported (Audio + Transcript) | Supported (Audio only) | Not supported (Presets) | Instant & Professional Cloning |
| **Sample Rate** | 24,000 Hz | 24,000 Hz | 24,000 Hz | 44,100 Hz |
| **License** | **MIT License** (Commercial Permissive) | **CPML** (Strictly Non-Commercial) | Microsoft Online Services | Commercial SaaS |
| **Commercial Readiness** | **Yes (`is_commercial_ready=True`)** | **No (`is_commercial_ready=False`)** | Yes | Yes |
| **Deployment Mode** | HTTP Sidecar or In-process | HTTP Sidecar or In-process | Cloud API (zero auth required) | Cloud SaaS |
| **Hardware Reqs** | GPU: 8GB+ VRAM or CPU sidecar | GPU: 8GB+ VRAM (NVIDIA CUDA) | Zero local compute | Zero local compute |

### 3.1 IndicF5 Architecture & Voice Cloning
- **Architecture**: Flow-matching diffusion transformer built on acoustic prefix matching.
- **Transcript Requirement**: For optimal acoustic alignment, IndicF5 voice enrollment accepts both reference audio (`audio_file_path`) and reference text (`reference_text`). If text is omitted, canonical Hindi/English phonetic pangrams are supplied by default.
- **Sidecar Microservice**: Because modern production environments (such as Python 3.13) can conflict with heavy CUDA C-extensions, IndicF5 is designed to operate primarily via a dedicated HTTP sidecar (`INDICF5_ENDPOINT_URL`). If the sidecar is unreachable, an in-process acoustic synthesizer acts as a graceful fallback.

### 3.2 Coqui XTTS & CPML Guardrails
- **Operational Reality**: Coqui AI dissolved in January 2024. The `xtts_v2` model weights are licensed under the **Coqui Public Model License (CPML)**, which prohibits commercial production without an explicit enterprise license.
- **Architectural Safeguard**: `CoquiXTTSProvider` flags `is_commercial_ready = False` in its capabilities. The application and health endpoint (`/voices/providers/health`) surface this warning clearly to prevent unintentional licensing non-compliance.
- **Recommended Alternative**: For commercial English voice cloning, the pipeline routes to ElevenLabs or F5-TTS / Kokoro.

---

## 4. Intelligent Routing (`VoiceRouter`)

The `VoiceRouter` (`backend/app/services/voice/router.py`) governs provider selection based on:
1. **Target Language & Script**:
   - Indian languages (`hi`, `ta`, `te`, `bn`, `mr`, `gu`, `kn`, `ml`, `pa`, `or`, `as`, `hinglish`) automatically prioritize `indicf5`.
   - English requests prioritize `coqui_xtts` (for local cloning) or `edge_tts` / `elevenlabs`.
2. **Capability Matching**:
   - Checks `provider.get_capabilities().supports(capability)`.
   - Requests for voice cloning filter out preset-only providers (such as Edge TTS).
3. **Explicit User Preference**:
   - If a caller supplies `preferred_provider`, it is placed at the head of the candidate list provided it supports the requested language and capability.
4. **Deterministic Failover**:
   - If the primary provider raises `VoiceProviderError` or times out (default: 30s), the router falls back to the next compatible provider.
   - **No Silent Intent Degradation**: If an unsupported language is requested (e.g. `fr` when only `hi` and `en` providers are loaded), the router raises a descriptive `VoiceProviderError` rather than silently replacing it with English.

---

## 5. Voice Cloning & Consent Verification

Voice cloning carries severe privacy and authenticity implications. Raghvi enforces the following safeguards:

1. **Mandatory Explicit Consent**:
   - Every cloning request (`POST /voices/upload`, `POST /voices/{id}/clone`, `VoiceCloneRequest`) requires `consent_confirmed = True`.
   - Requests without consent fail with HTTP 400 (`"Explicit user authorization and consent required"`).
2. **Media Validation**:
   - Supported containers: `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.mp4`, `.mov`, `.webm`.
   - Max file size: 20 MB.
   - Recommended duration: 45 to 120 seconds.
3. **Storage & Isolation**:
   - Raw recordings are uploaded to S3 under isolated prefixes: `voices/{user_id}/{voice_id}.{ext}`.
   - Private S3 URLs are never leaked in plain text; temporary presigned URLs (TTL: 24h) are generated on demand.
4. **Right to Deletion**:
   - `DELETE /voices/{id}` soft-deletes the database record and permanently purges the audio sample from S3.

---

## 6. How to Add a New Voice Provider

Adding a new voice provider requires four simple steps:

### Step 1: Create the Provider Class
Create `backend/app/services/voice/providers/my_provider.py` inheriting from `VoiceProvider`:

```python
from app.services.voice.providers.base import (
    VoiceProvider, ProviderCapabilities, VoiceCapability,
    VoiceSynthesisRequest, VoiceSynthesisResponse,
    VoiceCloneRequest, VoiceCloneResponse, VoiceProviderError,
)

class MyVoiceProvider(VoiceProvider):
    @property
    def provider_name(self) -> str:
        return "my_provider"

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            capabilities={VoiceCapability.TEXT_TO_SPEECH, VoiceCapability.STREAMING},
            supported_languages={"en", "hi", "es"},
            supported_audio_formats=["mp3", "wav"],
            sample_rates=[24000, 48000],
            is_commercial_ready=True,
            license_type="Commercial SaaS",
        )

    async def check_health(self) -> dict:
        return {"status": "ready", "provider": self.provider_name}

    async def synthesize_speech(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        # Implementation here
        return VoiceSynthesisResponse(audio_data=b"...", audio_format="wav", provider=self.provider_name)

    async def clone_voice(self, request: VoiceCloneRequest) -> VoiceCloneResponse:
        raise VoiceProviderError("Cloning not supported by MyVoiceProvider")
```

### Step 2: Register in `VoiceProviderFactory`
In `backend/app/services/voice/provider_factory.py`:

```python
from app.services.voice.providers.my_provider import MyVoiceProvider

_providers["my_provider"] = MyVoiceProvider
```

### Step 3: Add Configuration
In `backend/app/core/config.py`:
```python
my_provider_api_key: str = ""
```
And in `backend/app/services/voice/voice_adapter_builder.py`:
```python
elif name == "my_provider":
    if settings.my_provider_api_key:
        provider_configs.append({"name": "my_provider", "config": {"api_key": settings.my_provider_api_key}})
```

### Step 4: Add Automated Tests
Add test coverage in `backend/tests/test_voice_vendor_agnostic.py`.

---

## 7. Configuration Reference

```env
# Priority order (router tries compatible providers in this order)
VOICE_PROVIDER_PRIORITY=edge_tts,indicf5,elevenlabs,cartesia,deepgram,coqui_xtts

# IndicF5 Sidecar Configuration
INDICF5_ENDPOINT_URL=http://localhost:8008
INDICF5_MODEL_ID=ai4bharat/IndicF5

# Coqui XTTS Configuration
COQUI_XTTS_ENDPOINT_URL=http://localhost:8020
COQUI_MODEL_NAME=tts_models/multilingual/multi-dataset/xtts_v2

# Cloud API Keys
ELEVENLABS_API_KEY=
CARTESIA_API_KEY=
DEEPGRAM_API_KEY=
NVIDIA_API_KEY=

# Audio Configuration
VOICE_SAMPLE_RATE=24000
VOICE_FORMAT=wav
VOICE_CLONE_MAX_FILE_SIZE=20971520  # 20 MB
```

---

## 8. API Endpoints Reference

| Method | Route | Description |
| :--- | :--- | :--- |
| `GET` | `/voices/providers/capabilities` | Returns verified capabilities, formats, and licenses of all providers |
| `GET` | `/voices/providers/health` | Returns real-time health and readiness of all providers |
| `POST` | `/voices/synthesize` | Synthesizes text with automatic language/capability routing and failover |
| `POST` | `/voices/upload` | Uploads authorized voice reference media with consent verification |
| `POST` | `/voices/{id}/clone` | Activates synthetic voice enrollment |
| `GET` | `/voices` | Lists caller's active voices |
| `POST` | `/voices/{id}/set-default`| Selects default voice profile |
| `DELETE`| `/voices/{id}` | Permanently deletes voice profile and associated S3 media |
| `POST` | `/chat/send-with-voice` | Conversational response returned with aligned audio speech |

---

## 9. Verification & Testing

Run all voice architecture tests:
```bash
uv run pytest tests/test_voice_vendor_agnostic.py tests/test_voice_adapter_builder.py tests/test_voice_fallback.py tests/test_voice_api.py -v
```

Linting & formatting compliance:
```bash
uv run ruff check .
uv run ruff format --check .
```