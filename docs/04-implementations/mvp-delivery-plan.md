# Raghvi v2 — MVP Delivery Plan

**Status:** Active
**Date:** 2026-07-03
**Owner:** Vishal Singh Kushwaha
**Project:** Raghvi v2
**Architecture:** FastAPI + Python backend, Kotlin + Jetpack Compose Android client, PostgreSQL, provider-agnostic AI Gateway
**Local Runtime Standard:** Docker Compose for all backend-side services

---

## 1. Purpose

This document defines the implementation order for the Raghvi v2 MVP.

The MVP will not attempt to build a fully autonomous human-like assistant immediately. It will build a secure, reliable foundation and prove the core product loop:

```text
User talks to Raghvi
→ Raghvi understands the request
→ Raghvi uses relevant user memory
→ Raghvi gives a useful response
→ Raghvi proposes safe actions when appropriate
→ User remains in control
```

Each milestone must result in a working, demonstrable product increment.

---

## 2. MVP Success Criteria

The MVP is successful when a user can:

- Create and access an account.
- Chat with Raghvi from an Android application.
- Receive AI-generated responses through the backend.
- Save, view, edit, and delete selected memories.
- Ask Raghvi to remember a preference or important detail.
- Create and receive a simple reminder.
- Receive a proactive daily briefing only after explicit permission.
- Propose a supported Android action safely.
- Confirm or cancel high-risk actions before execution.
- Delete conversations, memories, or their account.
- Use the app without exposing secrets or allowing cross-user data access.

---

## 3. MVP Non-Goals

The MVP will not include:

- Fully autonomous messaging or calling.
- Financial transactions.
- Multi-agent autonomous workflows.
- Graph RAG or knowledge graph implementation.
- Complex calendar synchronization.
- Full WhatsApp automation.
- Voice assistant support.
- Web client.
- Multi-region infrastructure.
- Enterprise-scale microservices.
- Unlimited AI usage.
- Full social or emotional dependency features.
- User-selectable AI models for normal conversation.
- Autonomous high-risk device actions.

---

## 4. Delivery Principles

All implementation work must follow these rules:

- Build vertical slices, not disconnected layers.
- Finish one usable feature before starting several unfinished features.
- Keep API contracts documented.
- Write tests for critical behavior before calling a feature complete.
- Use feature flags for risky or incomplete capabilities.
- Never commit secrets.
- Keep commits small and meaningful.
- Prefer deterministic logic over LLMs when possible.
- Treat AI output as untrusted until validated.
- Do not add infrastructure complexity before the MVP needs it.
- Keep Raghvi as the single visible assistant identity.
- Do not expose internal model-provider routing during normal user conversation.
- Require explicit user confirmation for consequential actions.
- Keep local development reproducible through Docker Compose.

---

## 5. Local Development Runtime Standard

Raghvi v2 will follow a one-command local backend runtime standard.

The primary local development command will be:

```bash
docker compose up --build
```

This command must start all required backend-side services for local development.

Initially, this includes:

- PostgreSQL database
- FastAPI backend

Later, when needed, it may also include:

- Redis
- Background worker
- Scheduler
- Local observability tooling
- Mock external services

The Android application will run through Android Studio using an Android emulator or physical device. It will connect to the Dockerized backend through an environment-specific backend base URL.

The repository must provide:

- Root-level `compose.yaml`
- Root-level `.env.example`
- Backend `Dockerfile`
- Persistent Docker volumes for local database data
- Health checks for backend-dependent services
- Clear startup, shutdown, reset, and troubleshooting instructions in the root `README.md`

Recommended local commands:

```bash
docker compose up --build
docker compose down
docker compose down -v
docker compose logs -f backend
docker compose logs -f postgres
```

> `docker compose down -v` deletes Docker volumes and resets local database data. It must be used intentionally and documented clearly.

---

## 6. Repository and Test Organization

The repository will use clear separation between backend, Android, and cross-system tests.

```text
Raghvi-V2-The-AI-Assistant/
├── android/
│   └── app/
│       └── src/
│           ├── main/
│           ├── test/                  # Kotlin unit tests
│           └── androidTest/           # Android UI and instrumented tests
│
├── backend/
│   ├── app/
│   ├── alembic/
│   ├── tests/                         # FastAPI unit and integration tests
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── alembic.ini
│
├── docs/
│   ├── 00-projects/
│   ├── 01-products/
│   ├── 02-architecture/
│   ├── 03-decisions/
│   ├── 04-implementations/
│   └── 05-sprints/
│
├── infrastructure/
│   ├── docker/
│   └── deployment/
│
├── tests/
│   ├── e2e/                           # End-to-end user-flow tests
│   ├── contract/                      # Android ↔ backend API contract tests
│   └── fixtures/                      # Shared non-sensitive test data
│
├── compose.yaml
├── .env.example
├── .gitignore
└── README.md
```

**Rules:**

- Backend tests belong in `backend/tests/`.
- Android unit tests belong in `android/app/src/test/`.
- Android UI and instrumented tests belong in `android/app/src/androidTest/`.
- Root `tests/` is reserved for cross-system testing only.
- Test fixtures must never contain real personal data, secrets, tokens, or private conversations.
- Every critical API behavior must have backend test coverage.
- Every high-risk Android action flow must have Android UI or integration coverage before release.

---

## 7. Milestone Overview

| Milestone | Name | Primary Outcome |
|---|---|---|
| M0 | Repository and Development Foundation | Project runs locally and CI validates it |
| M1 | Identity and Secure API Foundation | Users can register, log in, and access protected APIs |
| M2 | Basic Raghvi Conversation | User can chat with Raghvi through Android |
| M3 | Memory Foundation | Raghvi can save and retrieve user-approved memory |
| M4 | Tasks and Reminders | User can create and manage reminders |
| M5 | Proactive Daily Briefing | Raghvi can provide permission-based proactive updates |
| M6 | Safe Android Actions | Raghvi can propose and safely execute supported actions |
| M7 | Privacy, Export, and Account Lifecycle | Users can control and delete their data |
| M8 | Staging Release and Portfolio Demo | MVP is deployed, tested, and documented |

---

### Milestone M0 — Repository and Development Foundation

**Goal**
Create a stable, reproducible local development environment before building product features.

**Deliverables**

*Backend*
- FastAPI project structure.
- Python dependency management using `pyproject.toml`.
- Environment configuration using `.env.example`.
- Backend Dockerfile.
- Docker Compose setup for backend and PostgreSQL.
- Health endpoint.
- Readiness endpoint.
- Basic application logging.
- Alembic migration setup.
- Database connection configuration.
- Linting and formatting configuration.
- Test framework setup.
- Basic backend test proving health endpoint behavior.

*Android*
- Kotlin Android project.
- Jetpack Compose setup.
- Basic navigation structure.
- Environment configuration for backend base URL.
- Debug build that runs on emulator.
- Basic API client setup.
- Error-state and loading-state UI components.
- Android unit-test setup.
- Android instrumented-test setup.

*Repository*
- Root README with local setup instructions.
- Root-level `compose.yaml`.
- Root-level `.env.example`.
- `.gitignore` verified.
- No secrets committed.
- GitHub Actions or equivalent CI pipeline.
- CI runs formatting, linting, tests, and backend build checks.
- Root test directory reserved for future end-to-end and contract testing.

**Definition of Done**

A new developer can clone the repository and run:

```bash
docker compose up --build
```

- PostgreSQL starts through Docker Compose.
- FastAPI starts through Docker Compose.
- Backend health endpoint responds successfully.
- Backend readiness endpoint verifies database connectivity.
- Android app launches in an emulator.
- Android can call the local backend health endpoint.
- CI passes on a clean pull request.
- A sample environment file exists without real secrets.
- Backend and Android test folders exist and can run at least one basic test.

---

### Milestone M1 — Identity and Secure API Foundation

**Goal**
Allow users to create accounts and access protected Raghvi resources securely.

**Deliverables**

*Backend*
- User database model.
- Alembic migration for users.
- Registration endpoint.
- Login endpoint.
- Password hashing.
- Access token and refresh token strategy.
- Protected `/me` endpoint.
- Logout and session revocation design.
- Ownership-check helper utilities.
- Authentication error handling.
- Login rate limiting.
- Authentication audit events.
- Backend tests for registration, login, protected access, and cross-user access prevention.

*Android*
- Welcome screen.
- Registration screen.
- Login screen.
- Secure token storage.
- Authenticated API client behavior.
- Logout flow.
- Loading and error states.
- Android tests for authentication UI states.

**API Scope**

```
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/users/me
```

**Definition of Done**

- A user can register and log in.
- A user can access their profile through a protected endpoint.
- Invalid credentials are rejected safely.
- Tokens are not logged.
- Android stores session tokens securely.
- One user cannot access another user's protected resources.
- Authentication tests pass.
- Logout revokes the active session correctly.

---

### Milestone M2 — Basic Raghvi Conversation

**Goal**
Deliver the first complete Raghvi experience: authenticated user chat through Android and AI-generated backend responses.

**Deliverables**

*Backend*
- Conversation model.
- Message model.
- Alembic migrations.
- Create conversation endpoint.
- Send message endpoint.
- Retrieve conversation history endpoint.
- AI Gateway module.
- One primary AI provider adapter.
- Configurable model settings.
- Request timeout and error handling.
- Privacy-safe AI telemetry.
- Basic response safety handling.
- Conversation ownership checks.
- Backend tests using a mocked AI Gateway.

*Android*
- Conversation list screen.
- Chat screen.
- Message composer.
- User and Raghvi message bubbles.
- Loading state while Raghvi responds.
- Retry state for failed requests.
- Conversation history display.
- Android tests for sending, loading, error, and retry states.

**API Scope**

```
POST   /api/v1/conversations
GET    /api/v1/conversations
GET    /api/v1/conversations/{conversation_id}
POST   /api/v1/conversations/{conversation_id}/messages
DELETE /api/v1/conversations/{conversation_id}
```

**Definition of Done**

- An authenticated user can create a conversation.
- The user can send a message from Android.
- The backend stores the message.
- Raghvi responds through the AI Gateway.
- The response is stored and displayed.
- Users can access only their own conversations.
- Failed AI requests show a safe error without pretending success.
- Conversation deletion removes it from normal retrieval.
- The app does not expose provider names or internal model routing during normal conversation.

---

### Milestone M3 — Memory Foundation

**Goal**
Allow Raghvi to remember user-approved information and use relevant memory in future conversations.

**Deliverables**

*Backend*
- Memory database model.
- Memory categories.
- Memory source tracking.
- Memory confidence and status fields.
- Create memory endpoint.
- List memory endpoint.
- Update memory endpoint.
- Delete memory endpoint.
- Memory retrieval service.
- Relevant-memory selection for chat context.
- Memory candidate extraction workflow.
- User confirmation requirement for selected memory categories.
- Deleted-memory exclusion from retrieval.
- Memory audit events.
- Backend tests for ownership, confirmation, deletion, and retrieval filtering.

*Android*
- Memory settings screen.
- Saved memories list.
- Edit memory flow.
- Delete memory flow.
- Memory confirmation UI when Raghvi proposes saving a memory.
- Android tests for memory confirmation and deletion flows.

**API Scope**

```
GET    /api/v1/memories
POST   /api/v1/memories
PATCH  /api/v1/memories/{memory_id}
DELETE /api/v1/memories/{memory_id}
POST   /api/v1/memories/candidates/{candidate_id}/confirm
POST   /api/v1/memories/candidates/{candidate_id}/reject
```

**Definition of Done**

- A user can manually save a memory.
- Raghvi can propose selected memories from conversation context.
- The user can confirm or reject proposed memories.
- Relevant active memories can influence a later conversation response.
- Deleted memories never appear in retrieval.
- Users can edit inaccurate memories.
- Memory ownership and privacy tests pass.
- External or untrusted content cannot automatically create durable memory.

---

### Milestone M4 — Tasks and Reminders

**Goal**
Enable practical everyday assistance through user-controlled reminders.

**Deliverables**

*Backend*
- Task model.
- Reminder model.
- Scheduled-job mechanism.
- Create, update, complete, and delete task endpoints.
- Create and delete reminder endpoints.
- Time-zone-aware reminder scheduling.
- Notification event model.
- Reminder execution audit event.
- Retry and failure behavior for scheduled jobs.
- Feature flag for reminder delivery if required.
- Backend tests for scheduling, cancellation, time zones, and account deletion behavior.

*Android*
- Task list screen.
- Create task flow.
- Reminder creation flow.
- Mark task complete flow.
- Notification permission request.
- Reminder notification display.
- Task and reminder settings.
- Android tests for task completion and reminder creation flows.

**API Scope**

```
GET    /api/v1/tasks
POST   /api/v1/tasks
PATCH  /api/v1/tasks/{task_id}
DELETE /api/v1/tasks/{task_id}

GET    /api/v1/reminders
POST   /api/v1/reminders
PATCH  /api/v1/reminders/{reminder_id}
DELETE /api/v1/reminders/{reminder_id}
```

**Definition of Done**

- A user can create a reminder through chat or UI.
- Reminder time is validated.
- Reminder triggers at the expected time.
- The user can cancel a reminder.
- Completed tasks do not appear as active tasks.
- Reminder failures are observable.
- No reminder is sent after account deactivation or deletion.
- Reminder behavior is tested using controlled time.

---

### Milestone M5 — Proactive Daily Briefing

**Goal**
Make Raghvi useful without requiring the user to ask every time.

**Deliverables**

*Backend*
- Proactive-intelligence preference model.
- Explicit opt-in flow.
- Daily briefing generation job.
- Relevant task and reminder retrieval.
- Basic special-date and event framework.
- Notification scheduling.
- Quiet-hours support.
- Proactive briefing audit events.
- Feature flag for proactive behavior.
- Rate limits and anti-spam controls.
- Backend tests for opt-in, quiet hours, disabling, and duplicate prevention.

*Android*
- Proactive assistance settings.
- Opt-in explanation.
- Notification schedule preference.
- Quiet-hours configuration.
- Daily briefing notification and screen.
- Android tests for preference changes.

**Definition of Done**

- Proactive behavior is disabled by default.
- A user can explicitly enable daily briefings.
- Raghvi can summarize relevant tasks and reminders.
- Quiet hours are respected.
- The user can disable briefings at any time.
- The system does not create unnecessary or repetitive notifications.
- Briefings do not expose private information on insecure notification surfaces.

---

### Milestone M6 — Safe Android Actions

**Goal**
Allow Raghvi to help with selected device actions while preserving user control.

**Initial Supported Actions**
- Open a supported app
- Create a reminder
- Draft an SMS
- Draft an email
- Open navigation to a destination

> Sending messages, placing calls, and other high-risk actions must remain confirmation-gated and may be deferred until Android platform constraints are fully understood.

**Deliverables**

*Backend*
- Action proposal model.
- Action risk classification.
- Action validation service.
- Action confirmation state machine.
- Audit events.
- Feature flags by action type.
- Safe failure handling.
- Permission and ownership checks.
- Backend tests for confirmation, cancellation, expiry, and failure states.

*Android*
- Action proposal UI.
- Confirm and cancel UI.
- Android intent integration for supported actions.
- Permission checks.
- Action completion and failure reporting.
- User-visible action history.
- Android tests for confirmation and cancellation flows.

**Action State Model**

```
proposed
awaiting_confirmation
confirmed
executing
completed
failed
cancelled
expired
```

**Definition of Done**

- Raghvi can propose an allowed action.
- The user sees a clear summary before confirmation.
- High-risk actions cannot execute without confirmation.
- Action results are accurately reported.
- Failed actions are never presented as completed.
- Users can revoke action permissions.
- Every action has an audit record.
- AI output cannot directly execute Android actions.

---

### Milestone M7 — Privacy, Export, and Account Lifecycle

**Goal**
Give users control over their data and align implementation with ADR-012.

**Deliverables**

- Conversation deletion.
- Memory deletion.
- Task and reminder deletion.
- Permission revocation.
- Account deactivation.
- Account deletion request.
- Session revocation.
- Background-job cancellation.
- Structured user-data export.
- Soft deletion cleanup job.
- Minimal audit event retention.
- Privacy settings screen.
- Backend tests for export ownership, deletion behavior, and session revocation.

**Definition of Done**

- Deleted memories are excluded from AI context.
- Deleted conversations are excluded from normal retrieval.
- Account deletion disables notifications and actions.
- Export contains only the requesting user's supported data.
- Data lifecycle tests pass.
- Deletion and export operations are audited safely.
- No deleted account can trigger background jobs.

---

### Milestone M8 — Staging Release and Portfolio Demo

**Goal**
Deploy a stable MVP and prepare it for demonstration.

**Deliverables**

- Staging environment.
- Production-like PostgreSQL setup.
- Managed secrets.
- Dockerized backend deployment.
- Health checks.
- Monitoring and error reporting.
- Android internal testing build.
- Demo account with synthetic data.
- Portfolio README.
- Architecture diagram.
- Feature walkthrough.
- Known limitations document.
- Demo video or screenshots.
- Security and privacy review checklist.
- End-to-end test coverage for the main user journey.

**Definition of Done**

- Staging backend is deployed securely.
- Android internal build connects to staging.
- Core user journey works end-to-end.
- No real secrets are included in the repository.
- Portfolio documentation explains technical decisions.
- Known limitations are documented clearly.
- A reviewer can understand, run, and evaluate the project.
- The project can be started locally using Docker Compose for backend-side services.

---

## 8. First Vertical Slice

The first implementation slice will be:

```text
User registration
→ user login
→ Android authenticated session
→ create conversation
→ send one message
→ backend calls AI Gateway
→ Raghvi response appears in Android chat
→ conversation persists
```

This slice proves the most important architecture path before memory, reminders, proactive behavior, or device actions are added.

---

## 9. Recommended Immediate Task Order

1. Create Sprint 00 foundation document.
2. Create root-level `compose.yaml`.
3. Create backend FastAPI project skeleton.
4. Add backend Dockerfile.
5. Add PostgreSQL service and persistent Docker volume.
6. Add FastAPI health endpoint.
7. Add FastAPI readiness endpoint with database connectivity check.
8. Configure Alembic.
9. Configure backend linting, formatting, and tests.
10. Create Android Kotlin + Jetpack Compose project.
11. Add Android navigation and API client foundation.
12. Configure Android debug backend base URL.
13. Configure CI for backend checks.
14. Verify `docker compose up --build` works from a clean clone.
15. Begin Milestone M1 authentication implementation.
16. Complete authentication before beginning conversation features.
17. Complete the first chat vertical slice before beginning memory.

---

## 10. Completion Rules for Every Feature

A feature is not complete merely because it works once on a developer machine.

Every completed feature must include:

- Backend implementation.
- Android implementation when user-facing.
- API contract.
- Input validation.
- Ownership and permission checks.
- Error states.
- Relevant tests.
- Logging or audit events where required.
- Documentation update if architecture or setup changed.
- Feature flag where risk or rollout control requires it.
- Clean Git commit.
- Verification through Dockerized local backend services.

---

## 11. Initial Backlog Labels

Use these labels in GitHub Issues or your task tracker:

**Type**
```
type: feature
type: bug
type: security
type: documentation
type: infrastructure
type: testing
```

**Area**
```
area: backend
area: android
area: ai
area: database
area: memory
area: reminders
area: actions
area: privacy
area: devops
```

**Priority**
```
priority: p0
priority: p1
priority: p2
```

**Milestone**
```
milestone: m0
milestone: m1
milestone: m2
milestone: m3
milestone: m4
milestone: m5
milestone: m6
milestone: m7
milestone: m8
```

---

## 12. Current Decision

The project will begin with Milestone M0, then move directly to Milestone M1.

No memory, proactive behavior, autonomous workflows, or Android actions will be implemented before authentication, secure API boundaries, Dockerized backend services, and the first chat vertical slice are working.