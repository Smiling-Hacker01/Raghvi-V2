# Raghvi V2 — The AI Assistant

Raghvi is a personal AI assistant project: an Android-first companion backed by a Python/FastAPI service, built as a modular monolith with PostgreSQL as its primary datastore.

This repository has completed **Sprint 01 (M1 – Identity and Secure API Foundation)** and **Sprint 02 (M2 – Conversational Chat API)**. The backend is now a fully functional, production-ready chat service with multi-provider AI failover, token-authenticated messaging, conversation history, and a comprehensive test suite (≥ 70% coverage). See `docs/05-sprints/` for sprint-level scope documents and `docs/04-implementations/mvp-delivery-plan.md` for the overall milestone roadmap.

## Architecture (current)

- **Backend:** Python 3.13, FastAPI, SQLAlchemy (async), PostgreSQL, Alembic for migrations
- **Dependency management:** [`uv`](https://docs.astral.sh/uv/)
- **Linting/formatting:** Ruff
- **Testing:** pytest + pytest-asyncio + pytest-cov (≥ 70% coverage enforced in CI)
- **Local orchestration:** Docker Compose
- **Android client:** Kotlin/Compose scaffold

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Git
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — only required if you want to run the backend directly on your machine (outside Docker), e.g. for running Alembic commands or tests locally

## Getting Started

### 1. Clone and configure environment

```powershell
git clone <repo-url>
cd Raghvi-V2-The-AI-Assistant
Copy-Item .env.example .env
Copy-Item backend\.env.example backend\.env   # if present; otherwise create manually — see below
```

The root `.env` configures PostgreSQL credentials used by Docker Compose. `backend/.env` is needed separately if you run backend tooling (Alembic, pytest) directly on your machine rather than inside Docker — it must point at the **host-mapped** Postgres port, not the internal Docker network address:

```env
DATABASE_URL=postgresql+asyncpg://raghvi:raghvi_dev_password@localhost:5435/raghvi
```

(Port `5435` is this project's current host-side mapping for Postgres — chosen to avoid colliding with other local Postgres installs. Check `compose.yaml` if unsure.)

You will also need AI provider API keys in `backend/.env` for the chat feature:

```env
AI_PROVIDER=gemini          # Primary provider: "openai" or "gemini"
OPENAI_API_KEY=sk-...       # Optional: enables OpenAI as primary or fallback
GEMINI_API_KEY=AIzaSy...    # Optional: enables Gemini as primary or fallback
```

If both keys are set, the backend automatically fails over from the primary to the fallback provider if the primary is down or rate-limited.

### 2. Start the backend stack

```powershell
docker compose up --build
```

This builds and starts two services: `postgres` and `backend`. The backend won't start until Postgres passes its healthcheck.

### 3. Run database migrations

```powershell
cd backend
uv run alembic upgrade head
```

### 4. Verify it's working

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

Both should return `200 OK`. `/health` confirms the process is alive; `/ready` confirms it can actually reach PostgreSQL.

## Common Commands

```bash
# Start the backend stack (Postgres + FastAPI)
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

# Run real LLM integration tests (requires API keys configured)
RUN_LLM_INTEGRATION_TESTS=1 uv run pytest tests/integration/ -v
```

## Backend Local Development (without Docker)

Useful for running Alembic migrations or the test suite directly:

```powershell
cd backend
uv sync
docker compose up -d postgres      # still need Postgres running
uv run alembic upgrade head
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

## Backend Auth API (Sprint 01)

Sprint 01 adds token-based authentication:

- `POST /auth/signup` creates a user and returns `access_token`, `refresh_token`, and `token_type`.
- `POST /auth/login` accepts username or email plus password and returns a new token pair.
- `POST /auth/refresh` validates and rotates a refresh token. The old refresh token is revoked.
- `POST /auth/logout` revokes the submitted refresh token.
- `POST /auth/revoke-all` revokes all active refresh tokens for the authenticated user.
- `GET /auth/me` returns the current user profile and requires `Authorization: Bearer <access_token>`.

Access tokens expire after 10 minutes by default. Refresh tokens expire after 14 days by default and are stored in the database as SHA-256 hashes, never as plaintext.

## Backend Chat API (Sprint 02)

Sprint 02 delivers the conversational core:

- `POST /chat/send` — sends a user message and returns the AI response. Requires a Bearer token. Returns the AI reply text, conversation ID, and token usage.
- `GET /chat/history` — paginated message history for the authenticated user's conversation. Supports `limit` and `before` query parameters.
- `GET /chat/conversation` — retrieves or lazily creates the user's conversation record.

### AI Provider Chain

The backend uses a **multi-provider failover architecture** so the app is never unavailable due to a single provider outage:

1. The **primary provider** is attempted first (configured via `AI_PROVIDER` env var).
2. If the primary fails (rate limit, timeout, API error), the next configured provider is tried **automatically and transparently** — Raghvi's personality is preserved because the same system prompt is reused for every attempt.
3. If all providers fail, a friendly, human-readable error message is returned. Provider names and technical details are never exposed to the user.

Providers currently supported: **OpenAI** (`gpt-4o` by default) and **Google Gemini** (`gemini-2.0-flash-lite` by default).

### Database Changes (Sprint 02)

- `Conversation` and `Message` models updated to use `String(36)` for IDs, aligned with JWT's string extraction of `user_id`.
- `UNIQUE` constraint added to `conversations.user_id` — one conversation per user.
- Race condition handling: if two simultaneous requests try to create the same conversation, the `IntegrityError` is caught and the existing record is returned safely.
- `created_at` / `updated_at` timestamps now use a timezone-aware-safe UTC helper, eliminating Python 3.12+ `datetime.utcnow()` deprecation warnings while remaining compatible with PostgreSQL's `TIMESTAMP WITHOUT TIME ZONE`.

### Testing (Sprint 02)

The test suite covers the entire application including the AI layer. All tests run without hitting real APIs (mocked), keeping the CI pipeline fast and free:

| Module | Strategy |
|---|---|
| Auth endpoints | Full async HTTP tests against an in-memory test DB |
| Chat endpoints | AI client mocked for speed and cost-free CI runs |
| `AIClient` | Unit tests with mocked `AIProviderChain` |
| `AIProviderChain` | Unit tests verifying primary success, failover, and total failure |
| `OpenAIAdapter` | Mocked `AsyncOpenAI` SDK — tests retry, rate-limit, and success paths |
| `GeminiAdapter` | Mocked `google.genai.Client` — tests success and rate-limit paths |

**Coverage threshold:** ≥ 70% enforced by `pytest-cov`. The build will fail if coverage drops below this. Current coverage: **~73%**.

**Real LLM integration tests** exist but are skipped by default (controlled by `RUN_LLM_INTEGRATION_TESTS=1` env var) to keep CI fast and free.

## Project Structure

```text
Raghvi-V2-The-AI-Assistant/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI route handlers (auth, chat, health, ready)
│   │   ├── core/            # Settings and configuration
│   │   ├── db/              # Database engine and async session factory
│   │   ├── middleware/       # JWT Bearer auth middleware
│   │   ├── models/           # SQLAlchemy ORM models (User, Conversation, Message)
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── security/         # JWT utilities and Argon2id password hashing
│   │   └── services/
│   │       ├── ai/           # Multi-provider AI chain (client, chain, adapters, prompt)
│   │       └── chat.py       # Chat business logic
│   ├── alembic/              # Database migration scripts
│   ├── tests/
│   │   ├── integration/      # Real LLM tests (skipped in CI by default)
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_chat.py
│   │   ├── test_chat_service.py
│   │   ├── test_ai_client.py
│   │   ├── test_ai_chain.py
│   │   └── test_ai_providers.py
│   └── pyproject.toml
├── android/                  # Android client (Kotlin/Compose scaffold)
├── docs/                     # Product, architecture, decisions, sprint plans
├── infrastructure/           # (reserved for future infra-as-code)
├── compose.yaml              # Local Docker orchestration
└── .env.example              # Template for local environment configuration
```

## Notes

- Line endings are normalized to LF via `.gitattributes` — if you're on Windows and see Ruff formatting complaints that don't match what's committed, check `git config core.autocrlf`.
- `alembic/versions/` is excluded from Ruff checks — auto-generated migration files aren't held to hand-written code style rules.
- The `AI_PROVIDER` env var controls which LLM is attempted first. Both providers can be configured simultaneously for automatic failover. If neither key is present, the backend will start but `/chat/send` will return a friendly configuration error.
