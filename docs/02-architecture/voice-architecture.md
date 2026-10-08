# Voice Architecture

## Overview

Raghvi's voice system provides **multi-provider speech synthesis with automatic failover**, **voice cloning**, and **subscription-gated access**. The architecture mirrors the AI provider chain pattern for reliability.

---

## Core Components

### 1. VoiceProvider (Abstract Base)

```python
class VoiceProvider(ABC):
    @abstractmethod
    async def synthesize_speech(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        ...
    
    @abstractmethod
    async def clone_voice(self, request: VoiceCloneRequest) -> VoiceCloneResponse:
        ...
    
    @abstractmethod
    def validate_config(self) -> bool:
        ...
```

**Location**: `backend/app/services/voice/providers/base.py`

### 2. Provider Implementations

| Provider | Class | Models | Features |
|----------|-------|--------|----------|
| ElevenLabs | `ElevenLabsProvider` | eleven_multilingual_v2, eleven_turbo_v2 | Premium, cloning, multilingual |
| Cartesia | `CartesiaProvider` | sonic, sonic-2 | Fast, low latency |
| Deepgram | `DeepgramProvider` | aura-asteria-en, aura-orpheus-en | TTS, streaming |
| Coqui XTTS | `CoquiXTTSProvider` | xtts_v2 | Open-source, self-hosted |

**Location**: `backend/app/services/voice/providers/`

### 3. VoiceProviderFactory (Dynamic Loading)

```python
class VoiceProviderFactory:
    @staticmethod
    def create_provider(name: str, config: dict) -> VoiceProvider:
        if name == "elevenlabs":
            return ElevenLabsProvider(config)
        elif name == "cartesia":
            return CartesiaProvider(config)
        elif name == "deepgram":
            return DeepgramProvider(config)
        elif name == "coqui_xtts":
            return CoquiXTTSProvider(config)
        raise ValueError(f"Unknown provider: {name}")
    
    @staticmethod
    def get_available_providers(config: dict) -> list[str]:
        # Returns list of providers with valid API keys
```

**Location**: `backend/app/services/voice/provider_factory.py`

### 4. VoiceAdapterBuilder (Failover Chain)

```python
class VoiceAdapterBuilder:
    def __init__(self, priority: list[str]):
        self.priority = priority  # From settings.voice_provider_priority
    
    def build(self) -> VoiceAdapter:
        # Creates chain similar to AIProviderChain
        # Tries providers in priority order on failure
```

**Location**: `backend/app/services/voice/voice_adapter_builder.py`

### 5. VoiceService (Business Logic)

```python
class VoiceService:
    # User voice management
    async def create_user_voice(...)
    async def get_user_voices(user_id, session)
    async def set_default_voice(voice_id, user_id, session)
    async def delete_user_voice(voice_id, user_id, session)
    async def expire_user_voices(user_id, session)  # On subscription downgrade
    
    # System voices
    async def get_system_voices(session, language=None)
    
    # Voice cloning
    async def clone_voice(user_id, voice_name, audio_path, provider, config, session)
    
    # Speech synthesis
    async def synthesize_speech(text, voice_id, user_id, provider, config, session)
```

**Location**: `backend/app/services/voice/voice_service.py`

---

## Request Flows

### Speech Synthesis (with Failover)

```
POST /voices/synthesize
    │
    ▼
VoiceService.synthesize_speech()
    │
    ▼
get_voice_adapter() ───► VoiceAdapterBuilder.build()
    │
    ▼
VoiceAdapter.synthesize_speech()
    │
    ├─► Try ElevenLabs (primary)
    ├─► On failure: try Cartesia
    ├─► On failure: try Deepgram
    └─► On failure: try Coqui XTTS
    │
    ▼
Return VoiceSynthesisResponse(audio_data, format, sample_rate)
    │
    ▼
API returns base64 audio
```

### Voice Cloning

```
POST /voices/upload (audio file → S3)
    │
    ▼
POST /voices/{voice_id}/clone
    │
    ▼
VoiceService.clone_voice()
    │
    ▼
1. Verify subscription allows custom voices
2. Download audio from S3
3. Call provider.clone_voice()
4. Create UserVoice record with provider voice_id
5. Set expires_at to subscription expiry
```

### Chat with Voice

```
POST /chat/send-with-voice
    │
    ▼
ChatService.send_message() ───► Get text response
    │
    ▼
VoiceService.synthesize_speech(voice_text, user's default voice)
    │
    ▼
Return {text_response, audio_base64, emotion, voice_text}
```

---

## Data Models

### UserVoice

```python
class UserVoice(Base):
    __tablename__ = "user_voices"
    
    id = Column(Uuid, primary_key=True, default=uuid4)
    user_id = Column(String(36), nullable=False, index=True)
    voice_type = Column(String(20), default="system")  # "system" or "custom"
    voice_id = Column(String(255), nullable=False)     # Provider-specific voice ID
    voice_name = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False)
    languages = Column(String(10), default="en")
    subscription_plan_id = Column(String(50), nullable=True)
    expires_at = Column(DateTime, nullable=True)       # Tied to subscription
    expires_with_subscription = Column(Boolean, default=True)
    audio_sample_url = Column(String(500), nullable=True)  # S3 URL
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)
    
    @property
    def is_available(self) -> bool:
        return self.is_active and self.deleted_at is None and \
               (self.expires_at is None or self.expires_at > now)
```

### SystemVoice

```python
class SystemVoice(Base):
    __tablename__ = "system_voices"
    
    id = Column(String(50), primary_key=True)  # Provider voice ID
    voice_name = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False)
    language = Column(String(10), default="en")
    quality_score = Column(Integer, default=50)  # 0-100 for sorting
    is_active = Column(Boolean, default=True)
```

---

## Subscription Gating

### Plan Limits

| Plan | Max Custom Voices | Voice Features |
|------|-------------------|----------------|
| Free | 0 | System voices only |
| Pro | 3 | Custom voices + cloning |
| Premium | 10 | Custom voices + cloning + priority |

### Enforcement Points

1. **Upload**: Check `plan.max_custom_voices` before allowing upload
2. **Clone**: Verify active subscription + voice quota
3. **Synthesize**: Allow system voices for all; custom voices require active subscription
4. **Downgrade/Cancel**: `VoiceService.expire_user_voices()` sets `expires_at = now`, `is_active = false`

---

## S3 Storage for Voice Samples

### S3Service

```python
class S3Service:
    async def upload_voice_sample(user_id, voice_id, audio_data, file_extension) -> str:
        # Key: voices/{user_id}/{voice_id}.{ext}
        # Returns: presigned URL or public URL
    
    async def delete_voice_sample(s3_url) -> None:
        # Parse key from URL, delete object
```

**Location**: `backend/app/services/storage/s3_service.py`

### Configuration

```env
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET=raghvi-voice-samples
S3_REGION=us-east-1
S3_VOICE_PREFIX=voices/
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/voices` | List user's voices |
| POST | `/voices/upload` | Upload voice sample (multipart) |
| POST | `/voices/{id}/clone` | Clone voice via provider |
| POST | `/voices/{id}/set-default` | Set default voice |
| DELETE | `/voices/{id}` | Delete voice (also removes S3 file) |
| GET | `/voices/system` | List available system voices |
| POST | `/voices/synthesize` | Synthesize speech (text → base64 audio) |

### Synthesis Request

```json
POST /voices/synthesize
Content-Type: multipart/form-data

text: "Hello, how can I help you?"
voice_id: "optional-voice-id"  // Uses default if omitted
language: "en"
```

### Synthesis Response

```json
{
  "success": true,
  "text": "Hello, how can I help you?",
  "voice_id": "EXAVITQu4vr4xnSDxMaL",
  "provider": "voice_synthesis",
  "audio_base64": "UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSuBzvLZiTYIG2m98OScTgwOUarm7blmGgU7k9n1unEiBC13yO/eizEIHWq+8+OWT",
  "audio_format": "wav",
  "sample_rate": 44100,
  "duration_estimate": 1.5
}
```

---

## Configuration

### Environment Variables

```env
# Voice provider priority (comma-separated, tried in order)
VOICE_PROVIDER_PRIORITY=elevenlabs,cartesia,deepgram,coqui_xtts

# Provider API keys
ELEVENLABS_API_KEY=...
ELEVENLABS_MODEL_ID=eleven_multilingual_v2

CARTESIA_API_KEY=...
CARTESIA_MODEL_ID=sonic

DEEPGRAM_API_KEY=...
DEEPGRAM_MODEL=aura-asteria-en

NVIDIA_API_KEY=...
NVIDIA_MODEL=fastpitch  # For Coqui/XTTS

# Voice synthesis settings
VOICE_SAMPLE_RATE=44100
VOICE_BIT_DEPTH=16
VOICE_CHANNELS=1
VOICE_FORMAT=wav

# Voice cloning limits
VOICE_CLONE_MIN_DURATION=45      # seconds
VOICE_CLONE_MAX_DURATION=120     # seconds
VOICE_CLONE_MAX_FILE_SIZE=20971520  # 20 MB

# S3
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET=...
S3_REGION=us-east-1
S3_VOICE_PREFIX=voices/

# Redis cache TTL for synthesized audio
REDIS_VOICE_CACHE_TTL=1800  # 30 minutes
```

---

## Multilingual Support

- ElevenLabs: `eleven_multilingual_v2` supports 29+ languages
- Deepgram: Aura voices primarily English, expanding
- Cartesia: Sonic supports multiple languages
- Coqui XTTS: 17 languages via `xtts_v2`

Language passed via `language` parameter in synthesis request (ISO 639-1 code).

---

## Emotion & Voice Text (from Chat)

Chat responses include XML tags parsed for voice synthesis:

```xml
<emotion>empathetic</emotion>
<voice_text>Soft, warm tone: "I understand how you feel."</voice_text>
<chat_text>I understand how you feel. Would you like to talk about it?</chat_text>
```

- `emotion`: Passed to providers that support emotion control (ElevenLabs)
- `voice_text`: Used for synthesis (can differ from chat text for prosody)
- `chat_text`: Shown to user in chat UI

---

## Testing

| Test | Coverage |
|------|----------|
| Provider adapters | Mock HTTP clients, test success/error paths |
| VoiceAdapterBuilder | Failover chain order, config validation |
| VoiceService | CRUD, quota enforcement, expiration logic |
| S3Service | Upload/download/delete with mocked boto3 |
| API endpoints | Auth, validation, subscription gating, error responses |

---

## Related ADRs

- [ADR-007: Android Device Integration](../03-decisions/ADR-007-android-device-integration-action.md)
- [ADR-011: Deployment, Secrets, Release Strategy](../03-decisions/ADR-011-deployment-environments-secrets-and-release-strategy.md)