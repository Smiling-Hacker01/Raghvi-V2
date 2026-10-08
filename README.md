# Raghvi V2 — The AI Assistant

Raghvi is a personal AI assistant: an Android-first companion backed by a Python/FastAPI service, built as a modular monolith with PostgreSQL as its primary datastore.

**Vision**: Help users *think better, remember what matters, and accomplish meaningful work* through natural conversation, long-term memory, reasoning, and secure task execution.

---

## Current Development Status

| Milestone | Name | Status |
|-----------|------|--------|
| M0 | Repository & Development Foundation | ✅ Complete |
| M1 | Identity & Secure API Foundation | ✅ Complete |
| M2 | Chat, Memory & Tasks | ✅ Complete |
| M3+ | Voice Synthesis & Subscriptions | ✅ Complete |

**Completed Sprints**: 00 → 05 (6 sprints total)
- Sprint 00: Foundation (Docker, FastAPI, Android scaffold, CI)
- Sprint 01: Authentication (JWT, Argon2id, refresh rotation, revocation)
- Sprint 02: Chat (multi-provider AI, failover, conversation history, Raghvi personality)
- Sprint 03: Memory System (sensitivity detection, TF-IDF retrieval, auto-extraction, encryption)
- Sprint 04: Tasks & Reminders (CRUD, priorities, due dates, auto-extraction, overdue alerts)
- Sprint 05: Voice & Payments (4-provider voice chain, cloning, Stripe subscriptions, plan-gated features)

---

## Architecture (Current)

### Backend
- **Runtime**: Python 3.13, FastAPI, SQLAlchemy (async), PostgreSQL 16, Alembic migrations
- **Dependency Management**: `uv`
- **Linting/Formatting**: Ruff
- **Testing**: pytest + pytest-asyncio + pytest-cov (≥70% coverage enforced in CI)
- **Local Orchestration**: Docker Compose

### AI Layer
- **Providers**: 7 providers with automatic failover — OpenAI, Google Gemini, Groq, GitHub Models, OpenRouter, HuggingFace
- **Pattern**: Adapter + Chain (primary → fallbacks, transparent to user)
- **Personality**: Raghvi system prompt injected on every request

### Memory System
- **Layers**: Working, Conversation, Episodic, Semantic, Project
- **Sensitivity Classification**: PUBLIC (auto-approved), SENSITIVE (pending approval), CRITICAL (encrypted, never auto-approved)
- **Retrieval**: TF-IDF semantic similarity (top-9 relevant memories per turn)
- **Auto-Extraction**: LLM-based fact extraction from chat messages

### Voice System
- **Providers**: ElevenLabs, Cartesia, Deepgram, Coqui XTTS (with failover)
- **Features**: Speech synthesis, voice cloning, multilingual support
- **Integration**: `/chat/send-with-voice` returns text + base64 audio

### Payments & Subscriptions
- **Provider**: Stripe (checkout, portal, webhooks)
- **Plans**: Free / Pro / Premium (voice quota, custom voice slots, daily message limits)
- **Gating**: Voice features restricted by plan tier

### Android Client
- **Stack**: Kotlin, Jetpack Compose, Material 3, Navigation Compose, Retrofit + OkHttp
- **Auth**: Encrypted token storage (Android Keystore), biometric gating, auto-refresh on 401
- **Screens**: Splash → Welcome → Login → Main (Chat, Memories, Tasks, Voices, Settings)

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Git
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — for running backend tooling locally (Alembic, pytest, Ruff)
- Android Studio (for Android development)

---

## Getting Started

### 1. Clone and Configure Environment

```powershell
git clone <repo-url>
cd Raghvi-V2-The-AI-Assistant
Copy-Item .env.example .env
Copy-Item backend\.env.example backend\.env   # if present; otherwise create manually — see below
```

**Root `.env`** (for Docker Compose):
```env
POSTGRES_USER=raghvi
POSTGRES_PASSWORD=raghvi_dev_password
POSTGRES_DB=raghvi
```

**Backend `.env`** (for local tooling — points at host-mapped Postgres port):
```env
DATABASE_URL=postgresql+asyncpg://raghvi:raghvi_dev_password@localhost:5435/raghvi
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# AI Providers (at least one required for chat)
AI_PROVIDER=gemini
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIzaSy...
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-...
HUGGINGFACE_API_KEY=hf_...
GITHUB_TOKEN=ghp_...

# Voice Providers (optional)
ELEVENLABS_API_KEY=...
CARTESIA_API_KEY=...
DEEPGRAM_API_KEY=...

# Payments (optional - for subscriptions)
PAYMENT_PROVIDER=stripe
STRIPE_API_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# AWS/S3 (for voice sample storage)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET=...
S3_REGION=us-east-1
```

> **Port Note**: PostgreSQL maps to host port `5435` (not 5432) to avoid conflicts. Check `compose.yaml` if unsure.

### 2. Start the Backend Stack

```powershell
docker compose up --build
```

This starts `postgres` (port 5435) and `backend` (port 8000). Backend waits for Postgres healthcheck.

### 3. Run Database Migrations

```powershell
cd backend
uv run alembic upgrade head
```

### 4. Verify It's Working

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

Both should return `200 OK`. `/health` = process alive; `/ready` = DB reachable.

### 5. Run Android App

Open `android/` in Android Studio. Build and run on emulator/device. The app connects to `http://10.0.2.2:8000` (emulator alias for host localhost).

---

## Common Commands

```bash
# Start backend stack (Postgres + FastAPI)
docker compose up --build

# Stop containers (keep data)
docker compose down

# Stop containers and wipe volumes (full reset)
docker compose down -v

# Tail logs
docker compose logs -f backend
docker compose logs -f postgres

# Run backend tests locally
cd backend
uv run pytest -v

# Run tests with coverage report
uv run pytest --cov=app --cov-report=term-missing

# Run linting
uv run ruff check .

# Run formatting
uv run ruff format .

# Run real LLM integration tests (requires API keys)
RUN_LLM_INTEGRATION_TESTS=1 uv run pytest tests/integration/ -v
```

---

## Backend Local Development (without Docker)

Useful for Alembic, tests, linting directly on host:

```powershell
cd backend
uv sync
docker compose up -d postgres      # still need Postgres running
uv run alembic upgrade head
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

---

## API Reference

### Authentication (`/auth`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/signup` | Register user, returns access + refresh tokens |
| POST | `/auth/login` | Login with username/email + password |
| POST | `/auth/refresh` | Rotate refresh token, get new access token |
| POST | `/auth/logout` | Revoke submitted refresh token |
| POST | `/auth/revoke-all` | Revoke all refresh tokens for user |
| GET | `/auth/me` | Get current user profile (requires Bearer token) |

**Tokens**: Access = 10 min, Refresh = 14 days (hashed in DB, rotated on use)

### Chat (`/chat`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat/send` | Send message, get AI response with memory context |
| POST | `/chat/send-with-voice` | Send message, get AI response + base64 audio |
| GET | `/chat/` | Get conversation metadata |
| GET | `/chat/history` | Paginated message history (newest first) |

**Features**: Multi-provider failover, memory retrieval (top-9), task context, Raghvi personality, friendly error responses

### Memories (`/memories`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/memories` | Create memory (auto-approval based on sensitivity) |
| GET | `/memories` | List approved memories |
| GET | `/memories/pending` | List pending approval memories |
| POST | `/memories/{id}/approve` | Approve/reject pending memory |
| DELETE | `/memories/{id}` | Delete approved memory (soft delete) |
| GET | `/memories/stats` | Memory counts (total, approved, pending, deleted) |

**Sensitivity**: PUBLIC (auto-approved) → SENSITIVE (pending) → CRITICAL (encrypted, never auto-approved)

### Tasks (`/tasks`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tasks` | Create task (title, description, priority, due_date, tags) |
| GET | `/tasks` | List tasks (filter: all/open/completed/overdue) |
| PATCH | `/tasks/{id}` | Update task |
| POST | `/tasks/{id}/complete` | Mark completed |
| DELETE | `/tasks/{id}` | Soft delete |
| GET | `/tasks/stats` | Task counts by status + overdue |

**Auto-extraction**: Tasks extracted from chat messages via LLM

### Voices (`/voices`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/voices` | List user's voices |
| POST | `/voices/upload` | Upload voice sample (requires subscription) |
| POST | `/voices/{id}/clone` | Clone voice via provider |
| POST | `/voices/{id}/set-default` | Set default voice |
| DELETE | `/voices/{id}` | Delete voice |
| GET | `/voices/system` | List system voices |
| POST | `/voices/synthesize` | Synthesize speech (text → audio) |

### Subscriptions (`/subscriptions`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/subscriptions/plans` | List available plans |
| GET | `/subscriptions/me` | Get current subscription |
| POST | `/subscriptions/upgrade` | Create Stripe checkout session to upgrade plan |
| POST | `/subscriptions/cancel` | Cancel subscription |
| GET | `/subscriptions/stats` | Subscription stats + voice quota |

### Webhooks (`/webhooks`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/webhooks/stripe` | Stripe events (checkout, subscription, payment) |

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe (DB connectivity) |

---

## Project Structure

```
Raghvi-V2-The-AI-Assistant/
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI routes (auth, chat, memories, tasks, voices, subscriptions, webhooks, health, ready)
│   │   ├── core/                   # Settings, config
│   │   ├── db/                     # Async engine, session, base model
│   │   ├── middleware/             # JWT auth middleware
│   │   ├── models/                 # SQLAlchemy models (User, Conversation, Message, Memory, Task, Reminder, Subscription, Voice, Creator)
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   ├── security/               # JWT, Argon2id password hashing
│   │   └── services/
│   │       ├── ai/                 # Multi-provider chain (client, chain, adapters, prompt, registry)
│   │       ├── memory/             # Memory service, retrieval (TF-IDF), extractor, encryption, rules
│   │       ├── voice/              # Voice service, providers (ElevenLabs, Cartesia, Deepgram, Coqui), adapter builder
│   │       ├── storage/            # S3 service for voice samples
│   │       ├── chat.py             # Chat business logic
│   │       ├── task_service.py     # Task CRUD, stats
│   │       ├── task_extractor.py   # LLM-based task extraction from chat
│   │       ├── reminder_service.py # Reminder creation, due-date alerts
│   │       ├── subscription_service.py # Plans, subscriptions, Stripe
│   │       └── creator_seed.py     # Singleton creator profile
│   ├── alembic/                    # Database migrations (9 migrations)
│   ├── tests/                      # Unit + integration tests (~70% coverage)
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── alembic.ini
├── android/
│   └── app/src/main/java/com/raghvi/assistant/
│       ├── network/                # Retrofit API, AuthInterceptor, TokenManager, BiometricManager
│       ├── ui/                     # Compose screens (Login, Chat, Memories, Tasks, Voices, Settings)
│       ├── navigation/             # NavGraph
│       └── theme/                  # Material 3 theming
├── docs/
│   ├── architecture/               # Architecture docs (to be created)
│   ├── api/                        # API reference (to be created)
│   ├── deployment/                 # Deployment guide (to be created)
│   ├── operations/                 # Operations guide (to be created)
│   ├── 00-projects/                # Vision, constitution, north star
│   ├── 01-products/                # User research, MVP definition
│   ├── 02-architecture/            # Architecture principles
│   ├── 03-decisions/               # ADRs (14 decisions)
│   ├── 04-implementations/         # Delivery plans
│   └── 05-sprints/                 # Sprint 00-05 documentation
├── infrastructure/                 # Reserved for future IaC
├── compose.yaml                    # Docker Compose (postgres + backend)
├── .env.example
└── README.md
```

---

## CI/CD Pipeline

**GitHub Actions** (`.github/workflows/backend-ci.yml`) — strict, hard-gate:

1. **Lint & Format** — Ruff lint + format check (blocking)
2. **Tests** — PostgreSQL service, Alembic migrations, pytest with ≥70% coverage (blocking)
3. **Docker Build** — Backend image builds and starts successfully (blocking)
4. **Secret Scan** — Gitleaks scan on full history (blocking)

No `continue-on-error` steps. PR cannot merge if any check fails.

---

## Technology Stack Summary

| Layer | Technology |
|-------|------------|
| Backend Runtime | Python 3.13, FastAPI |
| Database | PostgreSQL 16, SQLAlchemy 2.0 (async), Alembic |
| AI Providers | OpenAI, Gemini, Groq, GitHub Models, OpenRouter, HuggingFace |
| Voice Providers | ElevenLabs, Cartesia, Deepgram, Coqui XTTS |
| Payments | Stripe (checkout, portal, webhooks) |
| Storage | AWS S3 (voice samples) |
| Auth | JWT (HS256), Argon2id, refresh token rotation |
| Android | Kotlin, Jetpack Compose, Retrofit, OkHttp, AndroidX Security Crypto |
| CI/CD | GitHub Actions, Docker |
| Local Dev | Docker Compose, uv |

---

## Current Limitations & Known Gaps

- **Single conversation per user** (MVP design — one conversation per user)
- **Payment logic** — subscriptions are fully integrated with Stripe (checkout sessions and webhooks) using an adapter pattern.
- **Voice cloning** — `/voices/{id}/clone` endpoint stubbed, returns pending status
- **Android screens** — Memories, Tasks, Voices, Settings screens are scaffolded; full UI implementation in progress
- **No web client** — Android-only for MVP
- **No iOS** — out of scope for MVP
- **Memory embeddings** — TF-IDF only; pgvector/semantic search deferred
- **Background jobs** — No scheduler/worker yet (reminders, subscription expiry run on-demand or manual)

---

## Roadmap (Upcoming)

| Priority | Feature |
|----------|---------|
| P0 | Complete Android UI for Memories, Tasks, Voices, Settings |
| P0 | Implement voice cloning with ElevenLabs |
| P1 | Add pgvector for embedding-based memory retrieval |
| P1 | Background job scheduler (APScheduler or Celery) for reminders, subscription expiry |
| P1 | Proactive daily briefing (opt-in) |
| P2 | Android device actions (open app, draft SMS, navigation) |
| P2 | Conversation search/filtering |
| P2 | Data export (GDPR-compliant) |
| P3 | Web client (React/Next.js) |
| P3 | Multi-device sync |

---

## Documentation

| Document | Description |
|----------|-------------|
| `docs/00-projects/north-star.md` | Vision, mission, product identity |
| `docs/00-projects/product-brief.md` | Executive summary, MVP scope, success metrics |
| `docs/04-implementations/mvp-delivery-plan.md` | Milestone roadmap (M0–M8) |
| `docs/05-sprints/` | Sprint 00–05 detailed plans |
| `docs/03-decisions/` | 14 ADRs (memory, AI orchestration, auth, data storage, voice, deployment, etc.) |

---

## License

Proprietary — Portfolio project by Vishal Singh Kushwaha.

---

## Notes

- Line endings normalized to LF via `.gitattributes` — on Windows, check `git config core.autocrlf` if Ruff complains
- `alembic/versions/` excluded from Ruff checks (auto-generated migrations)
- `AI_PROVIDER` env var controls primary LLM; multiple keys enable automatic failover
- If no AI keys configured, backend starts but `/chat/send` returns friendly configuration error
- Creator profile (Vishal Singh Kushwaha) auto-seeded on every startup as singleton `id="1"`