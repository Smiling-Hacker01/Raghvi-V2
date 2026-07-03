# Raghvi v2 — MVP Delivery Plan

**Status:** Active
**Date:** 2026-07-03
**Owner:** Vishal Singh Kushwaha
**Project:** Raghvi v2
**Architecture:** FastAPI + Python backend, Kotlin + Jetpack Compose Android client, PostgreSQL, provider-agnostic AI Gateway

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

* Create and access an account.
* Chat with Raghvi from an Android application.
* Receive AI-generated responses through the backend.
* Save, view, edit, and delete selected memories.
* Ask Raghvi to remember a preference or important detail.
* Create and receive a simple reminder.
* Receive a proactive daily briefing only after explicit permission.
* Propose a supported Android action safely.
* Confirm or cancel high-risk actions before execution.
* Delete conversations, memories, or their account.
* Use the app without exposing secrets or allowing cross-user data access.

---

## 3. MVP Non-Goals

The MVP will not include:

* Fully autonomous messaging or calling.
* Financial transactions.
* Multi-agent autonomous workflows.
* Graph RAG or knowledge graph implementation.
* Complex calendar synchronization.
* Full WhatsApp automation.
* Voice assistant support.
* Web client.
* Multi-region infrastructure.
* Enterprise-scale microservices.
* Unlimited AI usage.
* Full social or emotional dependency features.

---

## 4. Delivery Principles

All implementation work must follow these rules:

* Build vertical slices, not disconnected layers.
* Finish one usable feature before starting several unfinished features.
* Keep API contracts documented.
* Write tests for critical behavior before calling a feature complete.
* Use feature flags for risky or incomplete capabilities.
* Never commit secrets.
* Keep commits small and meaningful.
* Prefer deterministic logic over LLMs when possible.
* Treat AI output as untrusted until validated.
* Do not add infrastructure complexity before the MVP needs it.

---

## 5. Milestone Overview

| Milestone | Name                                   | Primary Outcome                                         |
| --------- | -------------------------------------- | ------------------------------------------------------- |
| M0        | Repository and Development Foundation  | Project runs locally and CI validates it                |
| M1        | Identity and Secure API Foundation     | Users can register, log in, and access protected APIs   |
| M2        | Basic Raghvi Conversation              | User can chat with Raghvi through Android               |
| M3        | Memory Foundation                      | Raghvi can save and retrieve user-approved memory       |
| M4        | Tasks and Reminders                    | User can create and manage reminders                    |
| M5        | Proactive Daily Briefing               | Raghvi can provide permission-based proactive updates   |
| M6        | Safe Android Actions                   | Raghvi can propose and safely execute supported actions |
| M7        | Privacy, Export, and Account Lifecycle | Users can control and delete their data                 |
| M8        | Staging Release and Portfolio Demo     | MVP is deployed, tested, and documented                 |

---

# Milestone M0 — Repository and Development Foundation

## Goal

Create a stable local development environment before building product features.

## Deliverables

### Backend

* FastAPI project structure.
* Python dependency management.
* Environment configuration using `.env.example`.
* Dockerfile.
* Docker Compose setup for backend and PostgreSQL.
* Health endpoint.
* Readiness endpoint.
* Basic application logging.
* Alembic migration setup.
* Linting and formatting configuration.
* Test framework setup.

### Android

* Kotlin Android project.
* Jetpack Compose setup.
* Basic navigation structure.
* Environment configuration for backend base URL.
* Debug build that runs on emulator.
* Basic API client setup.
* Error-state and loading-state UI components.

### Repository

* Root README with local setup instructions.
* `.gitignore` verified.
* No secrets committed.
* GitHub Actions or equivalent CI pipeline.
* CI runs formatting, linting, tests, and backend build checks.

## Definition of Done

* A new developer can clone the repository and run the backend locally.
* PostgreSQL starts through Docker Compose.
* The backend health endpoint responds successfully.
* Android app launches in an emulator.
* CI passes on a clean pull request.
* A sample environment file exists without real secrets.

---

# Milestone M1 — Identity and Secure API Foundation

## Goal

Allow users to create accounts and access protected Raghvi resources securely.

## Deliverables

### Backend

* User database model.
* Alembic migration for users.
* Registration endpoint.
* Login endpoint.
* Password hashing.
* Access token and refresh token strategy.
* Protected `/me` endpoint.
* Logout and session revocation design.
* Ownership-check helper utilities.
* Authentication error handling.
* Login rate limiting.

### Android

* Welcome screen.
* Registration screen.
* Login screen.
* Secure token storage.
* Authenticated API client behavior.
* Logout flow.
* Loading and error states.

## API Scope

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/users/me
```

## Definition of Done

* A user can register and log in.
* A user can access their profile through a protected endpoint.
* Invalid credentials are rejected safely.
* Tokens are not logged.
* Android stores session tokens securely.
* One user cannot access another user’s protected resources.
* Authentication tests pass.

---

# Milestone M2 — Basic Raghvi Conversation

## Goal

Deliver the first complete Raghvi experience: authenticated user chat through Android and AI-generated backend responses.

## Deliverables

### Backend

* Conversation model.
* Message model.
* Alembic migrations.
* Create conversation endpoint.
* Send message endpoint.
* Retrieve conversation history endpoint.
* AI Gateway module.
* One primary AI provider adapter.
* Configurable model settings.
* Request timeout and error handling.
* Privacy-safe AI telemetry.
* Basic response safety handling.

### Android

* Conversation list screen.
* Chat screen.
* Message composer.
* User and Raghvi message bubbles.
* Loading state while Raghvi responds.
* Retry state for failed requests.
* Conversation history display.

## API Scope

```text
POST /api/v1/conversations
GET  /api/v1/conversations
GET  /api/v1/conversations/{conversation_id}
POST /api/v1/conversations/{conversation_id}/messages
DELETE /api/v1/conversations/{conversation_id}
```

## Definition of Done

* An authenticated user can create a conversation.
* The user can send a message from Android.
* The backend stores the message.
* Raghvi responds through the AI Gateway.
* The response is stored and displayed.
* Users can access only their own conversations.
* Failed AI requests show a safe error without pretending success.
* Conversation deletion removes it from normal retrieval.

---

# Milestone M3 — Memory Foundation

## Goal

Allow Raghvi to remember user-approved information and use relevant memory in future conversations.

## Deliverables

### Backend

* Memory database model.
* Memory categories.
* Memory source tracking.
* Memory confidence and status fields.
* Create memory endpoint.
* List memory endpoint.
* Update memory endpoint.
* Delete memory endpoint.
* Memory retrieval service.
* Relevant-memory selection for chat context.
* Memory candidate extraction workflow.
* User confirmation requirement for selected memory categories.
* Deleted-memory exclusion from retrieval.

### Android

* Memory settings screen.
* Saved memories list.
* Edit memory flow.
* Delete memory flow.
* Memory confirmation UI when Raghvi proposes saving a memory.

## API Scope

```text
GET    /api/v1/memories
POST   /api/v1/memories
PATCH  /api/v1/memories/{memory_id}
DELETE /api/v1/memories/{memory_id}
POST   /api/v1/memories/candidates/{candidate_id}/confirm
POST   /api/v1/memories/candidates/{candidate_id}/reject
```

## Definition of Done

* A user can manually save a memory.
* Raghvi can propose selected memories from conversation context.
* The user can confirm or reject proposed memories.
* Relevant active memories can influence a later conversation response.
* Deleted memories never appear in retrieval.
* Users can edit inaccurate memories.
* Memory ownership and privacy tests pass.

---

# Milestone M4 — Tasks and Reminders

## Goal

Enable practical everyday assistance through user-controlled reminders.

## Deliverables

### Backend

* Task model.
* Reminder model.
* Scheduled-job mechanism.
* Create, update, complete, and delete task endpoints.
* Create and delete reminder endpoints.
* Time-zone-aware reminder scheduling.
* Notification event model.
* Reminder execution audit event.
* Retry and failure behavior for scheduled jobs.

### Android

* Task list screen.
* Create task flow.
* Reminder creation flow.
* Mark task complete flow.
* Notification permission request.
* Reminder notification display.
* Task and reminder settings.

## API Scope

```text
GET    /api/v1/tasks
POST   /api/v1/tasks
PATCH  /api/v1/tasks/{task_id}
DELETE /api/v1/tasks/{task_id}

GET    /api/v1/reminders
POST   /api/v1/reminders
PATCH  /api/v1/reminders/{reminder_id}
DELETE /api/v1/reminders/{reminder_id}
```

## Definition of Done

* A user can create a reminder through chat or UI.
* Reminder time is validated.
* Reminder triggers at the expected time.
* The user can cancel a reminder.
* Completed tasks do not appear as active tasks.
* Reminder failures are observable.
* No reminder is sent after account deactivation or deletion.

---

# Milestone M5 — Proactive Daily Briefing

## Goal

Make Raghvi useful without requiring the user to ask every time.

## Deliverables

### Backend

* Proactive-intelligence preference model.
* Explicit opt-in flow.
* Daily briefing generation job.
* Relevant task and reminder retrieval.
* Basic special-date and event framework.
* Notification scheduling.
* Quiet-hours support.
* Proactive briefing audit events.
* Feature flag for proactive behavior.

### Android

* Proactive assistance settings.
* Opt-in explanation.
* Notification schedule preference.
* Quiet-hours configuration.
* Daily briefing notification and screen.

## Definition of Done

* Proactive behavior is disabled by default.
* A user can explicitly enable daily briefings.
* Raghvi can summarize relevant tasks and reminders.
* Quiet hours are respected.
* The user can disable briefings at any time.
* The system does not create unnecessary or repetitive notifications.

---

# Milestone M6 — Safe Android Actions

## Goal

Allow Raghvi to help with selected device actions while preserving user control.

## Initial Supported Actions

```text
Open a supported app
Create a reminder
Draft an SMS
Draft an email
Open navigation to a destination
```

Sending messages, placing calls, and other high-risk actions must remain confirmation-gated and may be deferred until Android platform constraints are fully understood.

## Deliverables

### Backend

* Action proposal model.
* Action risk classification.
* Action validation service.
* Action confirmation state machine.
* Audit events.
* Feature flags by action type.
* Safe failure handling.

### Android

* Action proposal UI.
* Confirm and cancel UI.
* Android intent integration for supported actions.
* Permission checks.
* Action completion and failure reporting.
* User-visible action history.

## Action State Model

```text
proposed
awaiting_confirmation
confirmed
executing
completed
failed
cancelled
expired
```

## Definition of Done

* Raghvi can propose an allowed action.
* The user sees a clear summary before confirmation.
* High-risk actions cannot execute without confirmation.
* Action results are accurately reported.
* Failed actions are never presented as completed.
* Users can revoke action permissions.
* Every action has an audit record.

---

# Milestone M7 — Privacy, Export, and Account Lifecycle

## Goal

Give users control over their data and align implementation with ADR-012.

## Deliverables

* Conversation deletion.
* Memory deletion.
* Task and reminder deletion.
* Permission revocation.
* Account deactivation.
* Account deletion request.
* Session revocation.
* Background-job cancellation.
* Structured user-data export.
* Soft deletion cleanup job.
* Minimal audit event retention.
* Privacy settings screen.

## Definition of Done

* Deleted memories are excluded from AI context.
* Deleted conversations are excluded from normal retrieval.
* Account deletion disables notifications and actions.
* Export contains only the requesting user’s supported data.
* Data lifecycle tests pass.
* Deletion and export operations are audited safely.

---

# Milestone M8 — Staging Release and Portfolio Demo

## Goal

Deploy a stable MVP and prepare it for demonstration.

## Deliverables

* Staging environment.
* Production-like PostgreSQL setup.
* Managed secrets.
* Dockerized backend deployment.
* Health checks.
* Monitoring and error reporting.
* Android internal testing build.
* Demo account with synthetic data.
* Portfolio README.
* Architecture diagram.
* Feature walkthrough.
* Known limitations document.
* Demo video or screenshots.

## Definition of Done

* Staging backend is deployed securely.
* Android internal build connects to staging.
* Core user journey works end-to-end.
* No real secrets are included in the repository.
* Portfolio documentation explains technical decisions.
* Known limitations are documented honestly.
* A reviewer can understand, run, and evaluate the project.

---

## 6. First Vertical Slice

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

## 7. Recommended Immediate Task Order

1. Create backend project skeleton.
2. Add Docker Compose and PostgreSQL.
3. Add FastAPI health endpoint.
4. Configure Alembic.
5. Create Android Kotlin + Jetpack Compose project.
6. Add Android navigation and API client foundation.
7. Configure CI.
8. Implement user model and authentication.
9. Build Android login and registration screens.
10. Implement conversation and message models.
11. Build the first chat screen.
12. Add the AI Gateway and primary provider adapter.
13. Complete the first vertical slice.
14. Demo it before starting memory.

---

## 8. Completion Rules for Every Feature

A feature is not complete merely because it works once on a developer machine.

Every completed feature must include:

* Backend implementation.
* Android implementation when user-facing.
* API contract.
* Input validation.
* Ownership and permission checks.
* Error states.
* Relevant tests.
* Logging or audit events where required.
* Documentation update if architecture or setup changed.
* Clean Git commit.

---

## 9. Initial Backlog Labels

Use these labels in GitHub Issues or your task tracker:

```text
type: feature
type: bug
type: security
type: documentation
type: infrastructure
type: testing

area: backend
area: android
area: ai
area: database
area: memory
area: reminders
area: actions
area: privacy

priority: p0
priority: p1
priority: p2

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

## 10. Current Decision

The project will begin with **Milestone M0**, then move directly to **Milestone M1**.

No memory, proactive behavior, autonomous workflows, or Android actions will be implemented before authentication, secure API boundaries, and the first chat vertical slice are working.
