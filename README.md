# Raghvi V2 — The AI Assistant

Raghvi is a personal AI assistant project: an Android-first companion backed by a Python/FastAPI service, built as a modular monolith with PostgreSQL as its primary datastore.

This repository is currently moving through **Sprint 01 (Milestone M1 - Identity and Secure API Foundation)**. The project provides a working local development environment, Android scaffold, database connectivity checks, migrations, linting, tests, and the first backend authentication endpoints. See `docs/05-sprints/sprint-o1-auth.md` for current sprint scope, and `docs/04-implementations/mvp-delivery-plan.md` for the overall milestone roadmap.

## Architecture (current)

- **Backend:** Python 3.13, FastAPI, SQLAlchemy (async), PostgreSQL, Alembic for migrations
- **Dependency management:** [`uv`](https://docs.astral.sh/uv/)
- **Linting/formatting:** Ruff
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

### 2. Start the backend stack

```powershell
docker compose up --build
```

This builds and starts two services: `postgres` and `backend`. The backend won't start until Postgres passes its healthcheck.

### 3. Verify it's working

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

Both should return `200 OK`. `/health` confirms the process is alive; `/ready` confirms it can actually reach PostgreSQL.

## Common Commands

```bash
# Start the backend-side environment (Postgres + FastAPI)
docker compose up --build

# Stop containers (keep data)
docker compose down

# Stop containers and wipe volumes (full reset)
docker compose down -v

# Tail logs
docker compose logs -f backend
docker compose logs -f postgres

# Run backend tests inside the container
docker compose exec backend pytest
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

## Backend Auth API

Sprint 01 adds token-based authentication:

- `POST /auth/signup` creates a user and returns `access_token`, `refresh_token`, and `token_type`.
- `POST /auth/login` accepts username or email plus password and returns a new token pair.
- `POST /auth/refresh` validates and rotates a refresh token. The old refresh token is revoked.
- `POST /auth/logout` revokes the submitted refresh token.
- `POST /auth/revoke-all` revokes all active refresh tokens for the authenticated user.
- `GET /auth/me` returns the current user profile and requires `Authorization: Bearer <access_token>`.

Access tokens expire after 10 minutes by default. Refresh tokens expire after 14 days by default and are stored in the database as SHA-256 hashes, never as plaintext.

## Project Structure

```text
Raghvi-V2-The-AI-Assistant/
├── backend/            # FastAPI service (Python, uv, SQLAlchemy, Alembic)
├── android/            # Android client (Kotlin/Compose)
├── docs/               # Product, architecture, decisions, sprint plans
├── infrastructure/     # (reserved for future infra-as-code)
├── tests/              # Cross-system tests only (e2e, contract, fixtures)
├── compose.yaml        # Local Docker orchestration
└── .env.example        # Template for local environment configuration
```


## Notes

- Line endings are normalized to LF via `.gitattributes` — if you're on Windows and see Ruff formatting complaints that don't match what's committed, check `git config core.autocrlf`.
- `alembic/versions/` is excluded from Ruff checks — auto-generated migration files aren't held to hand-written code style rules.
