# API Reference

## Base URL

| Environment | URL |
|-------------|-----|
| Local (Docker) | `http://localhost:8000` |
| Local (Android Emulator) | `http://10.0.2.2:8000` |
| Staging | `https://staging-api.raghvi.example.com` |
| Production | `https://api.raghvi.example.com` |

All endpoints prefixed with `/api/v1` in production (currently no prefix in local dev).

---

## Authentication

### Token Format

```
Authorization: Bearer <access_token>
```

### Token Lifetimes

| Token Type | Lifetime | Storage |
|------------|----------|---------|
| Access Token | 10 minutes | Client memory |
| Refresh Token | 14 days | HttpOnly cookie / Android Keystore |

### Refresh Flow

1. Access token expires (401 response)
2. Client calls `POST /auth/refresh` with refresh token
3. Server validates, rotates token (old revoked, new issued)
4. Client retries original request with new access token

---

## Error Responses

### Standard Format

```json
{
  "detail": "Human-readable error message"
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 204 | No Content (success) |
| 400 | Bad Request (validation) |
| 401 | Unauthorized (missing/invalid/expired token) |
| 403 | Forbidden (insufficient permissions/plan) |
| 404 | Not Found |
| 409 | Conflict (duplicate) |
| 422 | Unprocessable Entity (validation) |
| 429 | Too Many Requests (rate limited) |
| 500 | Internal Server Error |

---

## Endpoints

### Health & Readiness

#### GET /health
Liveness probe — process is running.

**Response**: `200 OK`
```json
{"service": "raghvi-backend", "status": "running"}
```

#### GET /ready
Readiness probe — database connectivity verified.

**Response**: `200 OK` or `503 Service Unavailable`
```json
{"status": "ready"}
```

---

### Authentication (`/auth`)

#### POST /auth/signup
Register a new user.

**Request**:
```json
{
  "username": "string (3-64 chars)",
  "email": "string (valid email)",
  "password": "string (8-256 chars)",
  "name": "string? (max 120)",
  "phone": "string? (max 32)",
  "preferences": "object? (default {})"
}
```

**Response**: `201 Created`
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer"
}
```

**Errors**: `409 Conflict` (username/email exists), `422` (validation)

---

#### POST /auth/login
Authenticate user.

**Request**:
```json
{
  "username": "string (username or email)",
  "password": "string"
}
```

**Response**: `200 OK`
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer"
}
```

**Errors**: `401 Unauthorized` (invalid credentials)

---

#### POST /auth/refresh
Rotate access token using refresh token.

**Request**:
```json
{
  "refresh_token": "string"
}
```

**Response**: `200 OK`
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer"
}
```

**Errors**: `401` (expired, revoked, invalid)

---

#### POST /auth/logout
Revoke a specific refresh token.

**Request**:
```json
{
  "refresh_token": "string"
}
```

**Response**: `204 No Content`

---

#### POST /auth/revoke-all
Revoke all refresh tokens for current user (password change, security).

**Headers**: `Authorization: Bearer <access_token>`

**Response**: `204 No Content`

---

#### GET /auth/me
Get current user profile.

**Headers**: `Authorization: Bearer <access_token>`

**Response**: `200 OK`
```json
{
  "id": "string",
  "username": "string",
  "email": "string",
  "name": "string|null",
  "phone": "string|null",
  "preferences": "object"
}
```

**Errors**: `401` (missing/invalid token)

---

### Chat (`/chat`)

#### POST /chat/send
Send message to Raghvi, get AI response with memory context.

**Headers**: `Authorization: Bearer <access_token>`

**Request**:
```json
{
  "content": "string (1-5000 chars)"
}
```

**Response**: `200 OK`
```json
{
  "user_message": "string",
  "assistant_message": "string",
  "voice_text": "string",        // For TTS (may differ from assistant_message)
  "emotion": "string",           // neutral, happy, sad, empathetic, etc.
  "tokens_used": "integer"
}
```

**Behavior**:
- Retrieves top-9 relevant memories (TF-IDF)
- Includes active tasks in context
- Multi-provider AI failover (transparent)
- Friendly error responses (never technical)
- Background: extracts memories & tasks from message

**Errors**: `422` (empty message), `500` (all AI providers failed → friendly message)

---

#### POST /chat/send-with-voice
Send message, get AI response + synthesized audio.

**Headers**: `Authorization: Bearer <access_token>`

**Request**:
```json
{
  "content": "string"
}
```

**Query Params**: `language` (default: "en")

**Response**: `200 OK`
```json
{
  "user_message": "string",
  "assistant_message": "string",
  "tokens_used": "integer",
  "audio": {
    "data_base64": "string",
    "format": "wav",
    "sample_rate": 44100,
    "provider": "voice_synthesis",
    "duration_estimate": "number"
  }
}
```

**Behavior**: Same as `/chat/send` + voice synthesis via multi-provider chain

---

#### GET /chat/
Get conversation metadata.

**Headers**: `Authorization: Bearer <access_token>`

**Response**: `200 OK`
```json
{
  "id": "string",
  "user_id": "string",
  "title": "string",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "message_count": "integer"
}
```

---

#### GET /chat/history
Get paginated conversation history.

**Headers**: `Authorization: Bearer <access_token>`

**Query Params**:
| Param | Type | Default | Max |
|-------|------|---------|-----|
| limit | integer | 20 | 100 |
| offset | integer | 0 | - |

**Response**: `200 OK`
```json
{
  "messages": [
    {
      "id": "string",
      "role": "user|assistant",
      "content": "string",
      "tokens_used": "integer|null",
      "created_at": "ISO8601"
    }
  ],
  "total": "integer",
  "has_more": "boolean"
}
```

**Ordering**: Messages returned chronological (oldest first) for UI display.

---

### Memories (`/memories`)

#### POST /memories
Create a memory (auto-detects sensitivity).

**Headers**: `Authorization: Bearer <access_token>`

**Request**:
```json
{
  "content": "string (1-10000 chars)"
}
```

**Response**: `201 Created`
```json
{
  "memory": {
    "id": "string",
    "content": "string",
    "is_sensitive": "boolean",
    "is_approved": "boolean",
    "created_at": "ISO8601",
    "updated_at": "ISO8601"
  },
  "is_auto_approved": "boolean",
  "severity_level": "public|sensitive|critical",
  "is_sensitive": "boolean",
  "requires_approval": "boolean",
  "total_score": "integer",
  "matched_rules": ["string"],
  "reason": "string"
}
```

**Auto-Approval Logic**:
- PUBLIC (score < 50): `is_auto_approved=true`, `approved_at=now`
- SENSITIVE (50-99): `is_auto_approved=false`, `approved_at=NULL` (pending)
- CRITICAL (≥100): `is_auto_approved=false`, encrypted if password provided

---

#### GET /memories
List approved memories.

**Headers**: `Authorization: Bearer <access_token>`

**Query Params**: `limit` (default 50, max 1000)

**Response**: `200 OK`
```json
{
  "memories": [
    {
      "id": "string",
      "content": "string",
      "is_sensitive": "boolean",
      "is_approved": true,
      "created_at": "ISO8601",
      "updated_at": "ISO8601"
    }
  ],
  "total": "integer",
  "approved_count": "integer",
  "pending_count": "integer",
  "deleted_count": "integer"
}
```

---

#### GET /memories/pending
List memories pending approval.

**Headers**: `Authorization: Bearer <access_token>`

**Response**: `200 OK` (same structure as `/memories`)

---

#### POST /memories/{memory_id}/approve
Approve or reject a pending memory.

**Headers**: `Authorization: Bearer <access_token>`

**Path**: `memory_id` (UUID)

**Request**:
```json
{
  "approved": "boolean"  // true = approve, false = reject (soft delete)
}
```

**Response**: `200 OK` (approve) or `204 No Content` (reject)
```json
{
  "id": "string",
  "content": "string",
  "is_sensitive": "boolean",
  "is_approved": true,
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

**Errors**: `404` (not found), `400` (already approved/deleted)

---

#### DELETE /memories/{memory_id}
Soft-delete an approved memory.

**Headers**: `Authorization: Bearer <access_token>`

**Path**: `memory_id` (UUID)

**Response**: `204 No Content`

**Errors**: `404` (not found), `400` (not approved/already deleted)

---

#### GET /memories/stats
Get memory statistics.

**Headers**: `Authorization: Bearer <access_token>`

**Response**: `200 OK`
```json
{
  "total": "integer",
  "approved": "integer",
  "pending": "integer",
  "deleted": "integer"
}
```

---

### Tasks (`/tasks`)

#### POST /tasks
Create a task.

**Headers**: `Authorization: Bearer <access_token>`

**Request**:
```json
{
  "title": "string (1-255 chars)",
  "description": "string? (max 2000)",
  "priority": "low|medium|high|urgent",
  "due_date": "ISO8601 date/time?",
  "tags": "string? (comma-separated)"
}
```

**Response**: `201 Created`
```json
{
  "id": "string",
  "title": "string",
  "description": "string|null",
  "status": "pending",
  "priority": "string",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "due_date": "ISO8601|null",
  "completed_at": "ISO8601|null",
  "tags": "string|null",
  "auto_extracted": "boolean"
}
```

---

#### GET /tasks
List tasks with filtering.

**Headers**: `Authorization: Bearer <access_token>`

**Query Params**: `status` (all|pending|in_progress|completed|overdue)

**Response**: `200 OK`
```json
{
  "tasks": [
    {
      "id": "string",
      "title": "string",
      "description": "string|null",
      "status": "string",
      "priority": "string",
      "created_at": "ISO8601",
      "updated_at": "ISO8601",
      "due_date": "ISO8601|null",
      "completed_at": "ISO8601|null",
      "tags": "string|null",
      "auto_extracted": "boolean"
    }
  ],
  "total": "integer",
  "pending_count": "integer",
  "in_progress_count": "integer",
  "completed_count": "integer"
}
```

---

#### PATCH /tasks/{task_id}
Update a task.

**Headers**: `Authorization: Bearer <access_token>`

**Path**: `task_id` (UUID)

**Request** (all optional):
```json
{
  "title": "string?",
  "description": "string?",
  "status": "pending|in_progress|completed?",
  "priority": "low|medium|high|urgent?",
  "due_date": "ISO8601?",
  "tags": "string?"
}
```

**Response**: `200 OK` (full task object)

**Errors**: `404` (not found)

---

#### POST /tasks/{task_id}/complete
Mark task as completed.

**Headers**: `Authorization: Bearer <access_token>`

**Path**: `task_id` (UUID)

**Response**: `200 OK` (full task object with `completed_at` set)

---

#### DELETE /tasks/{task_id}
Soft-delete a task.

**Headers**: `Authorization: Bearer <access_token>`

**Path**: `task_id` (UUID)

**Response**: `204 No Content`

---

#### GET /tasks/stats
Get task statistics.

**Headers**: `Authorization: Bearer <access_token>`

**Response**: `200 OK`
```json
{
  "total": "integer",
  "pending": "integer",
  "in_progress": "integer",
  "completed": "integer",
  "overdue": "integer"
}
```

---

### Voices (`/voices`)

#### GET /voices
List user's voices.

**Headers**: `Authorization: Bearer <access_token>`

**Response**: `200 OK`
```json
{
  "voices": [
    {
      "id": "string",
      "voice_name": "string",
      "voice_type": "system|custom",
      "provider": "string",
      "languages": "string",
      "is_active": "boolean",
      "is_default": "boolean",
      "is_available": "boolean",
      "audio_sample_url": "string|null",
      "created_at": "ISO8601",
      "expires_at": "ISO8601|null"
    }
  ],
  "total": "integer"
}
```

---

#### POST /voices/upload
Upload voice sample for cloning.

**Headers**: `Authorization: Bearer <access_token>`
**Content-Type**: `multipart/form-data`

**Form Fields**:
| Field | Type | Required |
|-------|------|----------|
| voice_name | string | Yes |
| audio_file | file (audio/*) | Yes |
| languages | string | No (default: "en") |

**Response**: `200 OK`
```json
{
  "voice_id": "string",
  "voice_name": "string",
  "audio_sample_url": "string",
  "status": "uploaded",
  "message": "Voice sample uploaded. Call /voices/{voice_id}/clone to create voice clone."
}
```

**Requirements**: Active Pro/Premium subscription, within voice quota
**Limits**: 45-120 seconds, max 20MB

---

#### POST /voices/{voice_id}/clone
Clone voice from uploaded sample.

**Headers**: `Authorization: Bearer <access_token>`

**Path**: `voice_id` (UUID)

**Response**: `200 OK`
```json
{
  "voice_id": "string",
  "status": "cloning_pending",
  "message": "Voice cloning started. This may take a few minutes."
}
```

**Note**: Actual provider cloning implementation pending; currently returns pending status.

---

#### POST /voices/{voice_id}/set-default
Set voice as default.

**Headers**: `Authorization: Bearer <access_token>`

**Path**: `voice_id` (UUID)

**Response**: `200 OK`
```json
{
  "voice_id": "string",
  "message": "Default voice updated"
}
```

---

#### DELETE /voices/{voice_id}
Delete a voice (also removes S3 audio sample).

**Headers**: `Authorization: Bearer <access_token>`

**Path**: `voice_id` (UUID)

**Response**: `200 OK`
```json
{
  "voice_id": "string",
  "message": "Voice deleted successfully"
}
```

---

#### GET /voices/system
List available system voices.

**Headers**: `Authorization: Bearer <access_token>`

**Query Params**: `language` (optional filter)

**Response**: `200 OK`
```json
{
  "voices": [
    {
      "id": "string",
      "voice_name": "string",
      "provider": "string",
      "language": "string",
      "quality_score": "integer"
    }
  ],
  "total": "integer"
}
```

---

#### POST /voices/synthesize
Synthesize speech from text.

**Headers**: `Authorization: Bearer <access_token>`
**Content-Type**: `multipart/form-data`

**Form Fields**:
| Field | Type | Required |
|-------|------|----------|
| text | string | Yes |
| voice_id | string | No (uses default) |
| language | string | No (default: "en") |

**Response**: `200 OK`
```json
{
  "success": true,
  "text": "string",
  "voice_id": "string",
  "provider": "voice_synthesis",
  "audio_base64": "string",
  "audio_format": "wav",
  "sample_rate": 44100,
  "duration_estimate": "number"
}
```

---

### Subscriptions (`/subscriptions`)

#### GET /subscriptions/plans
List available plans.

**Headers**: `Authorization: Bearer <access_token>`

**Response**: `200 OK`
```json
{
  "plans": [
    {
      "id": "string",
      "name": "string",
      "description": "string",
      "price_usd": "number",
      "billing_cycle": "monthly|yearly",
      "max_custom_voices": "integer",
      "supported_languages": "string",
      "daily_message_limit": "integer",
      "priority_support": "boolean",
      "family_sharing_slots": "integer"
    }
  ],
  "user_current_plan": "string|null"
}
```

---

#### GET /subscriptions/me
Get current subscription.

**Headers**: `Authorization: Bearer <access_token>`

**Response**: `200 OK`
```json
{
  "id": "string",
  "user_id": "string",
  "plan_id": "string",
  "plan_name": "string",
  "started_at": "ISO8601",
  "expires_at": "ISO8601",
  "is_active": "boolean",
  "is_expired": "boolean",
  "days_remaining": "integer",
  "auto_renew": "boolean",
  "stripe_subscription_id": "string|null"
}
```

**Errors**: `404` (no active subscription)

---

#### POST /subscriptions/upgrade
Create a payment checkout session to upgrade or subscribe to a plan.

**Headers**: `Authorization: Bearer <access_token>`

**Request**:
```json
{
  "plan_id": "string",
  "success_url": "string (URL)",
  "cancel_url": "string (URL)",
  "metadata": "object|null"
}
```

**Response**: `200 OK`
```json
{
  "provider_name": "string",
  "session_id": "string",
  "checkout_url": "string",
  "expires_at": "integer|null"
}
```

**Note**: This returns a checkout URL where the user securely enters their payment details. The local subscription will be activated automatically via webhook once the payment is completed.

---

#### POST /subscriptions/cancel
Cancel subscription.

**Headers**: `Authorization: Bearer <access_token>`

**Request**:
```json
{
  "reason": "string|null",
  "feedback": "string|null"
}
```

**Response**: `200 OK`
```json
{
  "status": "cancelled",
  "message": "Subscription cancelled successfully"
}
```

**Effect**: Deactivates subscription, expires custom voices

---

#### GET /subscriptions/stats
Get subscription statistics.

**Headers**: `Authorization: Bearer <access_token>`

**Response**: `200 OK`
```json
{
  "plan_id": "string",
  "plan_name": "string",
  "is_active": "boolean",
  "is_expired": "boolean",
  "days_remaining": "integer",
  "expires_at": "ISO8601",
  "voice_slots_used": "integer",
  "voice_slots_available": "integer",
  "auto_renew": "boolean"
}
```

---

### Webhooks (`/webhooks`)

#### POST /webhooks/stripe
Stripe webhook endpoint.

**Headers**: `Stripe-Signature: <signature>`

**Body**: Raw Stripe event JSON

**Events Handled**:
- `checkout.session.completed` → Activate subscription
- `customer.subscription.updated` → Update plan/status
- `customer.subscription.deleted` → Cancel subscription
- `invoice.payment_failed` → Handle failed payment

**Response**: `200 OK` (Stripe requires 2xx within 10s)

**Note**: Configure webhook URL in Stripe Dashboard: `https://your-domain/webhooks/stripe`

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/auth/login` | 5 req/min per IP |
| `/auth/signup` | 3 req/min per IP |
| `/chat/send` | 10 req/min per user |
| `/chat/send-with-voice` | 5 req/min per user |
| `/voices/synthesize` | 10 req/min per user |
| All others | 60 req/min per user |

Exceeded limits return `429 Too Many Requests` with `Retry-After` header.

---

## Pagination

List endpoints support:
- `limit` (default varies, max 100-1000)
- `offset` (default 0)

Response includes:
- `total`: Total count
- `has_more`: `(offset + limit) < total`

---

## Versioning

Current version: **v1** (no prefix in local, `/api/v1` in production)

Breaking changes will increment version. Non-breaking additions (new fields, endpoints) within same version.

---

## SDKs / Client Libraries

### Android (Kotlin)
- Retrofit + OkHttp + Kotlinx Serialization
- `RaghviApiService` interface in `android/app/src/main/java/com/raghvi/assistant/network/`
- `AuthInterceptor` handles token attachment + auto-refresh

### Python (Backend Testing)
- `httpx.AsyncClient` for integration tests
- See `backend/tests/conftest.py` for test client fixture

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01 | Initial: Auth, Chat |
| 1.1 | 2026-02 | Memories (CRUD, sensitivity, retrieval) |
| 1.2 | 2026-03 | Tasks, Reminders, Auto-extraction |
| 1.3 | 2026-04 | Voice synthesis, cloning, subscriptions |