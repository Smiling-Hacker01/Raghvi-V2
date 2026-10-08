# AI Architecture

## Overview

Raghvi uses a **multi-provider AI chain** with automatic failover to ensure the assistant is never unavailable due to a single provider outage. The system abstracts provider differences behind a unified adapter interface, preserving Raghvi's personality across all provider attempts.

---

## Core Components

### 1. AIProviderAdapter (Abstract Base)

```python
class AIProviderAdapter(ABC):
    @abstractmethod
    async def send_message(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, int]:  # (response_text, tokens_used)
        ...

    @abstractmethod
    def validate_config(self) -> bool:
        ...

    @abstractmethod
    def get_model_info(self) -> dict:
        ...
```

**Location**: `backend/app/services/ai/adapter.py`

### 2. Provider Implementations

| Provider | Adapter Class | Model | Key Features |
|----------|---------------|-------|--------------|
| OpenAI | `OpenAIAdapter` | gpt-4o | Primary premium option |
| Google Gemini | `GeminiAdapter` | gemini-2.0-flash | Free tier, fast |
| Groq | `GroqAdapter` | llama-3.3-70b-versatile | Ultra-fast inference |
| GitHub Models | `GitHubModelsAdapter` | gpt-4o | GitHub token auth |
| OpenRouter | `OpenRouterAdapter` | openai/gpt-4o-mini | Unified API for many models |
| HuggingFace | `HuggingFaceAdapter` | microsoft/Phi-3-mini-4k-instruct | Open-source models |

**Location**: `backend/app/services/ai/providers/`

### 3. AIProviderChain (Failover Orchestrator)

```python
class AIProviderChain:
    def __init__(self):
        self.primary_provider = settings.ai_provider  # From env
        self.provider_chain = self._build_chain()  # Ordered list
    
    async def send_message(self, messages, system_prompt, ...):
        for provider_name, adapter in self.provider_chain:
            try:
                return await adapter.send_message(...)
            except Exception:
                continue  # Try next provider
        raise RuntimeError("All providers failed")
```

**Location**: `backend/app/services/ai/chain.py`

**Failover Order**: Primary → Groq → GitHub → Gemini → OpenRouter → HuggingFace → OpenAI

### 4. AIClient (Business Logic Facade)

```python
class AIClient:
    def __init__(self):
        self.chain = AIProviderChain()
    
    async def send_message(self, messages, system_prompt, ...):
        return await self.chain.send_message(...)
```

**Location**: `backend/app/services/ai/client.py`

### 5. System Prompt Builder

```python
async def build_system_prompt(
    user_memories: list[Memory],
    session: AsyncSession,
    user_tasks: list[Task] = None,
) -> str:
    # 1. Base Raghvi personality
    # 2. Creator profile (singleton, cached)
    # 3. User profile (name, preferences)
    # 4. Relevant memories (top-9 from TF-IDF)
    # 5. Active tasks (due soon, overdue)
    # 6. Current date/time context
```

**Location**: `backend/app/services/ai/prompt.py`

---

## Request Flow

```
User Message
    │
    ▼
/chat/send endpoint
    │
    ▼
ChatService.send_message()
    │
    ├─► Get/create conversation (parallel)
    ├─► Retrieve relevant memories via TF-IDF (parallel)
    ├─► Get active tasks (parallel)
    │
    ▼
build_system_prompt() ───► Includes: personality + creator + profile + memories + tasks
    │
    ▼
get_ai_client().send_message()
    │
    ▼
AIProviderChain.send_message()
    │
    ├─► Try primary provider
    ├─► On failure: try Groq
    ├─► On failure: try GitHub Models
    ├─► On failure: try Gemini
    ├─► On failure: try OpenRouter
    ├─► On failure: try HuggingFace
    └─► On failure: try OpenAI
    │
    ▼
Parse XML response (<emotion>, <voice_text>, <chat_text>)
    │
    ▼
Store user + assistant messages
    │
    ▼
Background: Extract memories & tasks (non-blocking)
    │
    ▼
Return response
```

---

## Configuration

### Environment Variables

```env
# Primary provider (attempted first)
AI_PROVIDER=gemini

# Provider API keys (at least one required)
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIzaSy...
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-...
HUGGINGFACE_API_KEY=hf_...
GITHUB_TOKEN=ghp_...

# Model overrides (optional)
OPENAI_MODEL=gpt-4o
GEMINI_MODEL=gemini-2.0-flash
GROQ_MODEL=llama-3.3-70b-versatile
OPENROUTER_MODEL=openai/gpt-4o-mini
HUGGINGFACE_MODEL=microsoft/Phi-3-mini-4k-instruct
GITHUB_MODEL=gpt-4o

# Timeouts (seconds)
OPENAI_TIMEOUT_SECONDS=15
GEMINI_TIMEOUT_SECONDS=15
GROQ_TIMEOUT_SECONDS=15
...
```

### Settings Class

**Location**: `backend/app/core/config.py`

All provider keys loaded via `pydantic-settings` from `.env`.

---

## Error Handling

### Provider Errors (caught and trigger failover)

- Rate limits (429)
- Timeouts (>15s default)
- Authentication failures (401)
- Quota exceeded
- Network errors
- Invalid responses

### User-Facing Errors (never technical)

All provider failures return friendly messages via `get_error_response()`:

| Scenario | Response |
|----------|----------|
| LLM timeout | "Sorry, I got distracted for a moment. Can you repeat that?" |
| All providers down | "My mind just went blank. Can you try that again in a moment?" |
| Config error | "I'm having trouble getting started. Please check your AI provider configuration." |

**Location**: `backend/app/services/ai/prompt.py`

---

## Testing Strategy

| Layer | Approach |
|-------|----------|
| Adapters | Mock SDK clients (AsyncOpenAI, google.genai, etc.) |
| Chain | Unit tests: primary success, failover, total failure |
| Client | Integration tests with mocked chain |
| Endpoints | Mock AIClient, test full flow |

**Coverage Target**: ≥70% (enforced in CI)

---

## Adding a New Provider

1. Create adapter in `backend/app/services/ai/providers/<name>.py`
2. Implement `AIProviderAdapter` interface
3. Add import and loading logic in `AIProviderChain._load_provider()`
4. Add provider to `fallback_order` list in `AIProviderChain._build_chain()`
5. Add environment variables to `Settings` and `.env.example`
6. Write unit tests for adapter
7. Update documentation

---

## Related ADRs

- [ADR-002: AI Orchestration](../03-decisions/ADR-002-ai-orchestration.md)
- [ADR-013: AI Model Provider Strategy](../03-decisions/ADR-013-ai-model-provider-strategy-cost-controls-and-fallbacks.md)