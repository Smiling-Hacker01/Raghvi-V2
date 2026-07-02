# ADR-008 — API Contracts, Client Communication, and Error Handling

**Status:** Accepted
**Date:** 2026-07-02
**Decision Owners:** Vishal Singh Kushwaha
**Related Documents:**

* `docs/03-decisions/ADR-003-backend-framework-and-runtime.md`
* `docs/03-decisions/ADR-005-authentication-authorization-and-privacy.md`
* `docs/03-decisions/ADR-007-android-device-action-integration.md`

---

## Context

Raghvi v2 has an Android client and a FastAPI backend. The client will depend on backend APIs for authentication, conversations, memory, reminders, proactive briefings, permissions, confirmations, and structured device-action instructions.

As the project grows, API inconsistency can create fragile mobile releases, difficult debugging, duplicate actions, unclear error states, and accidental exposure of internal backend details.

The API must therefore be treated as a product contract, not merely a collection of routes.

---

## Problem Statement

How should Raghvi define, version, validate, secure, document, and evolve API communication between the Android client and the FastAPI backend?

---

## Decision

Raghvi will use a **versioned REST API with schema-first contracts, consistent error envelopes, idempotency for mutation endpoints, and backend-generated request correlation IDs**.

The FastAPI backend will expose APIs under a versioned prefix:

```text
/api/v1
```

Pydantic models will define request and response schemas. The Android client will use typed DTOs that mirror stable API contracts but remain separate from internal backend domain models.

The backend will generate OpenAPI documentation automatically and use it as the source for API discovery and contract verification.

---

## API Design Principles

Raghvi APIs must be:

* User-scoped and authorization-aware
* Explicit about request and response shapes
* Stable within an API version
* Consistent in naming and pagination
* Safe to retry where appropriate
* Clear about errors
* Observable through request IDs
* Minimal in exposed internal details
* Backward compatible when practical
* Designed around user-facing capabilities rather than database tables

---

## API Base Structure

```text id="k4fqyg"
https://api.raghvi.example/api/v1
```

Initial resource groups:

```text id="d44om8"
/auth
/users
/conversations
/messages
/memories
/projects
/tasks
/reminders
/briefings
/permissions
/confirmations
/actions
/audit-events
```

Example routes:

```text id="dqtw6h"
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout

POST   /api/v1/conversations
GET    /api/v1/conversations/{conversation_id}
POST   /api/v1/conversations/{conversation_id}/messages

GET    /api/v1/memories
PATCH  /api/v1/memories/{memory_id}
DELETE /api/v1/memories/{memory_id}

GET    /api/v1/reminders
POST   /api/v1/reminders
PATCH  /api/v1/reminders/{reminder_id}

GET    /api/v1/briefings/today

GET    /api/v1/permissions
PATCH  /api/v1/permissions/{permission_type}

POST   /api/v1/actions/{action_id}/confirm
POST   /api/v1/actions/{action_id}/outcomes
```

---

## Request and Response Contract Rules

### Request Rules

* Use JSON request bodies for structured data.
* Use path parameters for resource identity.
* Use query parameters for filtering, sorting, and pagination.
* Validate all request payloads with Pydantic.
* Reject unknown or malformed fields where strictness is appropriate.
* Never trust `user_id` from a request body when authentication already establishes the user.
* Use ISO 8601 timestamps with timezone offsets.
* Use explicit enums for finite state values.

### Response Rules

* Return predictable JSON objects.
* Use stable field names.
* Use `snake_case` in backend API JSON unless the Android serialization strategy deliberately maps it.
* Include resource identifiers and timestamps where useful.
* Avoid exposing internal exception details.
* Return only the data needed by the client.
* Keep internal database schema separate from API response schemas.

---

## Standard Success Response

For single-resource responses, return the resource directly.

```json id="xnvwxz"
{
  "id": "memory_01HXYZ",
  "type": "preference",
  "content": "The user prefers concise technical explanations.",
  "confidence": 0.92,
  "importance": 0.7,
  "status": "active",
  "created_at": "2026-07-02T10:30:00Z",
  "updated_at": "2026-07-02T10:30:00Z"
}
```

For collection responses, use a consistent envelope.

```json id="0s0q5z"
{
  "items": [
    {
      "id": "memory_01HXYZ",
      "type": "preference",
      "content": "The user prefers concise technical explanations."
    }
  ],
  "pagination": {
    "limit": 20,
    "next_cursor": "cursor_value_or_null"
  }
}
```

---

## Standard Error Envelope

All API errors must follow a consistent structure.

```json id="qnqc1t"
{
  "error": {
    "code": "MEMORY_NOT_FOUND",
    "message": "The requested memory could not be found.",
    "request_id": "req_01HXYZ",
    "details": []
  }
}
```

The `message` should be safe to show to users or map to a user-friendly Android message.

The `details` field may contain validation information but must not expose secrets, stack traces, tokens, database internals, or private data.

---

## HTTP Status Code Policy

| Status Code                 | Usage                                                 |
| --------------------------- | ----------------------------------------------------- |
| `200 OK`                    | Successful read, update, or action outcome retrieval  |
| `201 Created`               | New resource created                                  |
| `202 Accepted`              | Request accepted for asynchronous processing          |
| `204 No Content`            | Successful deletion with no response body             |
| `400 Bad Request`           | Invalid request shape or unsupported input            |
| `401 Unauthorized`          | Missing, invalid, or expired authentication           |
| `403 Forbidden`             | Authenticated user lacks permission                   |
| `404 Not Found`             | Resource does not exist or is not visible to the user |
| `409 Conflict`              | Duplicate, stale, or conflicting state                |
| `422 Unprocessable Entity`  | Validation failure                                    |
| `429 Too Many Requests`     | Rate limit exceeded                                   |
| `500 Internal Server Error` | Unexpected server error                               |
| `503 Service Unavailable`   | Temporary dependency or service failure               |

The backend must not use `200 OK` for failed operations merely because a JSON response was returned.

---

## Error Code Strategy

Error codes must be stable and machine-readable.

Examples:

```text id="sppqaj"
AUTH_INVALID_CREDENTIALS
AUTH_TOKEN_EXPIRED
AUTH_SESSION_REVOKED

MEMORY_NOT_FOUND
MEMORY_DELETE_NOT_ALLOWED
MEMORY_VALIDATION_FAILED

PERMISSION_DENIED
PERMISSION_NOT_GRANTED
CONFIRMATION_EXPIRED
CONFIRMATION_DENIED

ACTION_NOT_FOUND
ACTION_UNSUPPORTED
ACTION_EXPIRED
ACTION_OUTCOME_INVALID

RATE_LIMIT_EXCEEDED
REQUEST_IDEMPOTENCY_CONFLICT
INTERNAL_ERROR
DEPENDENCY_UNAVAILABLE
```

The Android client should map known error codes to appropriate UI states. Unknown error codes should fall back to a safe generic message.

---

## Idempotency Policy

Mutation endpoints that may be retried due to mobile-network failure must support idempotency.

The Android client will send an idempotency key for applicable requests:

```text id="p2v9y2"
Idempotency-Key: unique-client-generated-value
```

The backend will store the key, request fingerprint, and resulting response for a limited retention period.

Idempotency is especially important for:

* Creating reminders
* Sending a conversation message
* Creating confirmation requests
* Reporting device-action outcomes
* Creating projects or tasks
* Triggering asynchronous jobs

If the same key is reused with a different payload, the backend must return a conflict error.

---

## Request Correlation and Observability

Every backend request must have a request ID.

Rules:

* The backend generates a request ID if the client does not provide one.
* The backend returns the request ID in response headers.
* The backend includes the request ID in error envelopes.
* Logs, audit events, and background-job events should reference the request ID where applicable.
* The Android client may display the request ID in a support or diagnostics screen in the future.

Example response header:

```text id="ad3qku"
X-Request-ID: req_01HXYZ
```

---

## Authentication Header

Authenticated requests will use a bearer token.

```text id="f6p3qy"
Authorization: Bearer <access_token>
```

Rules:

* Tokens must be transmitted only over HTTPS.
* Tokens must not be placed in query parameters.
* Tokens must not be logged.
* Android must refresh tokens through the defined refresh flow.
* The backend must return a clear authentication error when a token is expired or revoked.

---

## Pagination Strategy

Collection endpoints must use cursor-based pagination when collections can grow.

Example:

```text id="q5f2oy"
GET /api/v1/memories?limit=20&cursor=next_cursor_value
```

Response:

```json id="7i4q2u"
{
  "items": [],
  "pagination": {
    "limit": 20,
    "next_cursor": "next_cursor_value_or_null"
  }
}
```

Cursor pagination is preferred because it is more stable than offset pagination when records are created or deleted while a user is scrolling.

---

## Filtering and Sorting Rules

Filtering and sorting must be explicit and limited to supported fields.

Examples:

```text id="l1r4zj"
GET /api/v1/memories?type=preference&status=active
GET /api/v1/tasks?project_id=project_01&status=in_progress
GET /api/v1/audit-events?from=2026-07-01T00:00:00Z
```

The backend must validate filters and reject unsupported fields rather than silently ignoring them.

---

## API Versioning Strategy

The API will use URI versioning.

```text id="3n5l4m"
/api/v1
```

Rules:

* Breaking changes require a new major API version.
* Additive fields may be introduced within the same version when clients can ignore unknown fields safely.
* Deprecated endpoints must have a migration plan before removal.
* The Android client should be able to support the current and previous stable API version during transition periods when practical.
* Internal backend refactoring must not change public API behavior without an explicit contract update.

---

## OpenAPI Documentation

FastAPI-generated OpenAPI documentation will be available in development environments.

The OpenAPI specification will be used for:

* API discovery
* Manual testing
* Android integration reference
* Contract review
* Future client generation if needed
* Documentation validation in CI

The project should keep endpoint descriptions, examples, error responses, and authentication requirements current.

---

## Android Client Communication Rules

The Android client will:

* Use a typed HTTP client such as Retrofit.
* Define request and response DTOs separately from UI models.
* Use an interceptor for authentication headers.
* Use an interceptor for request IDs and idempotency keys where required.
* Handle token refresh in a controlled authentication flow.
* Map API errors into stable UI states.
* Avoid retrying non-idempotent operations blindly.
* Show clear loading, success, retry, and failure states.
* Avoid exposing raw backend errors directly to users.

---

## Retry Policy

The Android client may retry safe requests when appropriate.

Safe retry examples:

* Idempotent GET requests
* Requests with an idempotency key
* Temporary network failures
* `503 Service Unavailable` responses with backoff guidance

The client must not automatically retry:

* Confirmation approvals
* External actions
* Authentication credential submission
* Requests that may create duplicate effects without idempotency protection

Retries should use exponential backoff and stop after a limited number of attempts.

---

## Asynchronous Operations

Long-running operations may return `202 Accepted`.

Example:

```json id="gpdz5g"
{
  "job_id": "job_01HXYZ",
  "status": "queued",
  "request_id": "req_01HXYZ"
}
```

The client can then poll a job-status endpoint or use a future real-time channel.

The MVP should avoid making normal chat responses asynchronous unless necessary.

---

## Alternatives Considered

### Option A — Unversioned REST API

**Advantages**

* Less initial routing setup
* Faster early experimentation

**Disadvantages**

* Breaking changes become risky
* Android releases may become incompatible
* Harder to evolve safely

**Decision:** Rejected.

### Option B — GraphQL from the Start

**Advantages**

* Flexible client queries
* Strong schema tooling
* Useful for complex multi-client data access

**Disadvantages**

* More infrastructure and learning overhead
* Less direct fit for command-style actions and confirmation workflows
* Adds complexity before the API surface is stable

**Decision:** Deferred.

### Option C — Versioned REST API with OpenAPI

**Advantages**

* Clear and familiar mobile integration
* Strong FastAPI support
* Easy request validation
* Straightforward security and observability
* Good fit for resource operations and action commands

**Disadvantages**

* May require additional endpoints as product complexity grows
* Requires discipline to maintain contract quality

**Decision:** Accepted.

---

## Consequences

### Positive Consequences

* Android and backend can evolve with clearer boundaries.
* API failures become easier to debug through request IDs.
* Idempotency reduces duplicate actions on unreliable mobile networks.
* Stable error codes improve Android UX.
* Versioning reduces risk from backend changes.
* OpenAPI improves documentation and integration speed.

### Negative Consequences

* API contracts require ongoing maintenance.
* Idempotency storage adds backend work.
* Versioning requires deprecation discipline.
* Typed DTOs create some duplication between backend and Android.
* The team must resist exposing internal models directly.

---

## MVP Scope

The MVP will include:

* `/api/v1` versioned REST API
* Pydantic request and response schemas
* Standard error envelope
* Stable error codes
* Request IDs
* Bearer-token authentication
* Cursor pagination for growing collections
* Idempotency for selected mutation endpoints
* FastAPI OpenAPI documentation
* Typed Android DTOs and Retrofit integration
* Basic retry handling

The MVP will not include:

* GraphQL
* Public third-party API access
* Webhooks
* Full SDK generation
* WebSocket-first communication
* Complex API gateway infrastructure
* Multi-region API routing

---

## Future Evolution

Future versions may add:

* WebSocket or Server-Sent Events for streaming
* GraphQL for selected read-heavy use cases
* Public developer API
* Webhooks for approved integrations
* Automated client generation from OpenAPI
* Advanced rate limiting
* API analytics and performance dashboards
* Feature flags and API capability negotiation
* Contract testing between backend and Android

---

## Decision Gate

This ADR is accepted when the project agrees that:

* APIs are versioned under `/api/v1`.
* Pydantic schemas define stable request and response contracts.
* Errors use a consistent envelope and stable error codes.
* Request IDs are required for observability.
* Idempotency protects retryable mutation endpoints.
* Android uses typed DTOs and does not depend on backend internals.
* OpenAPI documentation is maintained as part of the API contract.

---

## Interview Talking Points

* Why use REST and OpenAPI for Android-backend communication?
* How do idempotency keys prevent duplicate reminders or actions?
* Why are request IDs useful in distributed debugging?
* How do you version an API without breaking existing mobile clients?
* Why use cursor pagination instead of offset pagination?
* How do stable error codes improve the Android user experience?
* Why should API DTOs remain separate from database models?
