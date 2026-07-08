# Sprint 00 — Foundation

**Milestone:** M0 — Repository and Development Foundation
**Sprint Goal:** Establish a reproducible local development environment covering FastAPI, PostgreSQL, Docker Compose, the Android project foundation, baseline tests, and CI — with nothing beyond foundation scope.

---

## 1. Objective

By the end of this sprint, a fresh clone of the repository must allow:

- A single command (`docker compose up --build`) to start PostgreSQL and the FastAPI backend.
- The backend to expose a working `/health` and `/ready` endpoint.
- The Android app to build, run in an emulator, and successfully call the Dockerized backend.
- Backend code to be linted, formatted, and tested automatically in CI.
- Android code to compile locally with at least minimal test coverage.

No authentication, chat, memory, tasks, or AI-layer work belongs in this sprint. This is infrastructure only.

---

## 2. Scope

### 2.0 CI/CD Platform & Quality Bar

- **CI/CD platform:** GitHub Actions.
- **Quality bar:** CI is a hard gate, not advisory. The pipeline must fail the build (block merge) on any of the following, with zero tolerance / no "warn-only" steps:
  - Ruff lint errors (including unused imports, unreachable code, complexity warnings we enable)
  - Ruff format check failures (formatting must be applied, not just checked loosely)
  - Any failing or skipped-without-reason Pytest test
  - Backend Docker image failing to build
  - Type errors (mypy or pyright will be introduced no later than Sprint 01 for this reason — flagged here, not implemented yet)
  - Any committed secret pattern (basic secret-scanning step included even at this stage)
- No step in CI may be configured with `continue-on-error: true` or equivalent unless explicitly discussed and justified in this document.
- "Buggy code" is defined operationally for this sprint as: code that fails lint, fails format check, fails a test, or fails to build the Docker image. CI enforces all four before merge is allowed.
- This strictness bar applies from Sprint 00 onward and is not something later sprints are expected to loosen.

### 2.1 In Scope

**Backend foundation**
- FastAPI project skeleton
- `pyproject.toml`-based dependency management
- Environment configuration (`.env` support, no secrets committed)
- Backend `Dockerfile`
- Root-level `compose.yaml`
- PostgreSQL Docker service with named volume
- FastAPI Docker service
- `GET /health` (liveness — no dependencies checked)
- `GET /ready` (readiness — verifies PostgreSQL connectivity)
- SQLAlchemy async engine/session configuration
- Alembic initialized and configured for async SQLAlchemy
- Ruff configured for linting and formatting
- Pytest configured
- At least one backend test (health endpoint)

**Android foundation**
- Kotlin Android project
- Jetpack Compose + Material 3
- Navigation Compose
- Screens: `SplashScreen`, `WelcomeScreen`, `BackendStatusScreen`
- Retrofit + OkHttp API client
- Backend base URL injected via build configuration (`10.0.2.2:8000` for emulator)
- One Android unit test
- One Android instrumented/UI test

**Docker & local runtime**
- Root-level `compose.yaml` with `postgres` and `backend` services
- Named volume for PostgreSQL data
- Backend exposes port `8000`
- Backend connects to PostgreSQL over the Compose network
- Documented commands (see Section 5)

**CI (GitHub Actions, strict/hard-gate — see Section 2.0)**
- Backend format check (Ruff format) — blocking
- Backend lint check (Ruff lint) — blocking
- Backend test run (Pytest) — blocking, no skipped tests
- Backend Docker build validation — blocking
- Basic secret-scan step — blocking
- No real secrets in CI config
- Android CI may be deferred; Android must still compile locally

### 2.2 Out of Scope (explicitly deferred)

- Authentication / identity (M1)
- Chat or AI Gateway integration (M2)
- Memory system (M3)
- Tasks/reminders (M4)
- Proactive briefings (M5)
- Android device actions (M6)
- Privacy/export/account lifecycle (M7)
- Staging deployment (M8)
- Any MVP non-goal listed in the project vision document

---

## 3. Deliverables

| # | Deliverable | Location |
|---|---|---|
| 1 | Sprint 00 plan (this document) | `docs/05-sprints/sprint-00-foundation.md` |
| 2 | Docker Compose config | `compose.yaml` |
| 3 | FastAPI backend skeleton | `backend/` |
| 4 | Backend Dockerfile | `backend/Dockerfile` |
| 5 | Alembic setup | `backend/alembic/`, `backend/alembic.ini` |
| 6 | Backend tests | `backend/tests/` |
| 7 | Android project | `android/` |
| 8 | Android tests | `android/app/src/test/`, `android/app/src/androidTest/` |
| 9 | CI workflow | `.github/workflows/` (or equivalent, confirmed in that step) |
| 10 | Updated root `README.md` with setup instructions | `README.md` |

---

## 4. Task Breakdown (execution order — matches project task order)

1. Create and commit `docs/05-sprints/sprint-00-foundation.md` ✅ *(this document)*
2. Create root-level `compose.yaml`
3. Create FastAPI backend skeleton
4. Add backend `Dockerfile`
5. Add PostgreSQL service + named volume to `compose.yaml`
6. Implement `GET /health`
7. Implement `GET /ready` (PostgreSQL check)
8. Configure Alembic (async)
9. Configure Ruff (lint + format) and Pytest; add health endpoint test
10. Update root `README.md` with setup instructions
11. Add baseline backend CI
12. Create Android Kotlin + Jetpack Compose project
13. Add Android navigation + API client foundation
14. Verify Android emulator can call the Dockerized backend
15. Verify `docker compose up --build` works from a clean clone
16. Sprint 00 closes → begin M1 (authentication)

Each step will be delivered individually with: files changed, exact commands, expected output, a verification checklist, and a suggested Git commit message. No step begins until the previous one is confirmed complete.

---

## 5. Standard Local Commands (to be documented in README)

```bash
# Start backend-side environment (Postgres + FastAPI)
docker compose up --build

# Stop containers (keep volumes/data)
docker compose down

# Stop containers and remove volumes (full reset)
docker compose down -v

# Tail backend logs
docker compose logs -f backend

# Tail Postgres logs
docker compose logs -f postgres

# Run backend test suite inside the container
docker compose exec backend pytest
```

Android connects to the backend via `http://10.0.2.2:8000` when run in the emulator (this is the emulator's alias for the host machine's `localhost`).

---

## 6. Acceptance Criteria (Definition of Done for Sprint 00)

- [x] `docker compose up --build` succeeds from a clean clone with no manual steps beyond documented prerequisites (Docker Desktop installed).
- [x] `GET http://localhost:8000/health` returns `200 OK`.
- [x] `GET http://localhost:8000/ready` returns `200 OK` only when PostgreSQL is reachable, and a non-200 status when it is not.
- [x] `docker compose exec backend pytest` passes with at least one test covering `/health`.
- [x] Ruff lint and format checks pass with zero errors.
- [x] Alembic can generate and apply a no-op migration against the Dockerized PostgreSQL instance.
- [x] Android project builds successfully in Android Studio.
- [x] Android `BackendStatusScreen` successfully calls `/health` against the Dockerized backend from a physical device and displays the result.
- [x] At least one Android unit test and one instrumented test pass.
- [x] CI pipeline runs format, lint, test, and Docker build checks on push/PR, **every check is blocking** (no `continue-on-error`), and a PR cannot merge if any check fails.
- [x] Root `README.md` accurately documents setup and the commands in Section 5.
- [x] No files or folders exist outside what this sprint requires (no premature M1+ scaffolding).
---

## 7. Risks / Notes

- **Windows development environment:** All commands provided during this sprint will include PowerShell-compatible equivalents where they differ from POSIX shells.
- **Async Alembic + SQLAlchemy:** Requires careful config (async engine vs. Alembic's default sync migration runner) — this trade-off will be explained explicitly when we reach that step rather than glossed over.
- **Android CI deferral:** Permitted per project scope, but local compilation is still mandatory before Sprint 00 is considered closed.
- **Scope discipline:** Any request that resembles M1+ work (auth, users table, tokens) surfacing during this sprint should be flagged and deferred, not silently absorbed into Sprint 00.

---

## 8. Exit Condition

Sprint 00 is complete only when every item in Section 6 is checked and you have explicitly confirmed completion. Only then does work begin on M1 — Identity and Secure API Foundation.