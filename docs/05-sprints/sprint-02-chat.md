# Sprint 02 — Basic Chat & Message History

**Milestone:** M2 (Chat, Memory, Tasks)  
**Sprint Goal:** Users can chat with Raghvi, receive responses, and view conversation history. Raghvi always remembers the user via system prompt.

---

## 1. Objective

By the end of this sprint:

- Users can send messages and receive Raghvi responses (via OpenAI adapter)
- Conversations and messages persist in database
- Message history is accessible and paginated
- Raghvi's personality is established (friend, never breaks character, includes user profile context)
- Error responses are friendly and human-like (never technical)
- LLM provider is abstracted via adapter/plugin pattern (swappable in future)

---

## 2. Scope

### 2.1 In Scope

**Backend — Database & Models**
- `Conversation` model: `id`, `user_id`, `title`, `created_at`, `updated_at` (one per user)
- `Message` model: `id`, `conversation_id`, `role` (user/assistant), `content`, `tokens_used`, `created_at`
- Alembic migration for both tables + indexes

**Backend — LLM Adapter Pattern**
- `app/services/ai/adapter.py` — abstract `AIProviderAdapter` base class
  - Methods: `send_message(messages, system_prompt) -> response`
  - Methods: `validate_config() -> bool`
  - Methods: `get_model_info() -> dict`
- `app/services/ai/providers/openai.py` — OpenAI adapter implementation
  - Uses OpenAI client library
  - Handles token counting (track usage)
  - Implements retry logic with backoff
  - Configurable model (default: gpt-4-turbo or gpt-3.5-turbo)
- `app/services/ai/registry.py` — plugin registry
  - Loads adapter based on `AI_PROVIDER` env var
  - Fallback to OpenAI if not specified
- `app/services/ai/client.py` — business logic client
  - Depends only on adapter interface, not implementation
  - Handles context management (last 20 messages + user profile memory)

**Backend — Chat Endpoints**
- `POST /chat/send` — accept user message, call LLM, store both, return response
  - Request: `{"content": "user message"}`
  - Response: `{"user_message": "...", "assistant_message": "...", "tokens_used": 123}`
  - Include user profile memory in system prompt (even in Sprint 02, before Memory system)
  - Handle errors gracefully (friendly response, log error)
- `GET /chat/history` — paginated conversation history
  - Query params: `limit=20&offset=0`
  - Response: `{"messages": [...], "total": 100, "has_more": true}`
  - Newest messages first
- `GET /chat/` — get conversation metadata
  - Response: `{"id": "...", "user_id": "...", "created_at": "...", "message_count": 42}`

**Backend — System Prompt & Personality**
- Base system prompt template (Raghvi as friend, never breaks character)
- User profile context injection (name, background, communication style)
- Prompt management: allow future customization per user (M5+)
- System prompt stored in env config or database (decide in implementation)

**Backend — Error Handling**
- LLM timeout (>15s) → friendly response + log
- LLM API errors (quota, auth, etc.) → friendly response + alert ops
- Rate limiting (10 req/min) → friendly response, queue or reject
- Database errors → friendly response + log
- Invalid request → friendly response with clarification

**Backend — Testing**
- Unit tests: AIProviderAdapter interface and OpenAI adapter
  - Mock OpenAI API responses
  - Test retry logic, token counting
- Unit tests: Conversation/Message model creation
- Integration tests: `/chat/send` endpoint (mocked LLM)
  - Verify message storage (user + assistant)
  - Verify response format
  - Verify error handling (timeout, API error, etc.)
- Integration tests: `/chat/history` endpoint
  - Verify pagination
  - Verify ordering (newest first)
  - Verify filtering by user

**Android — Chat Screen**
- `ChatScreen.kt` — main chat UI
  - Message list (scrollable, lazy-loaded for large histories)
  - Input field at bottom
  - Send button
  - Loading indicator while waiting for response
  - Timestamp on each message
  - Distinguish user vs assistant messages (different bubbles/colors)
- `ChatMessage.kt` — composable for individual message
  - Display content, timestamp, role indicator
- Network integration:
  - Call `POST /chat/send` on send button tap
  - Parse response, add to local list
  - Auto-scroll to latest message
  - Show error toast on failure (friendly message)

**Android — Conversation Loading**
- On app startup: check if conversation exists
  - If yes: load and display history
  - If no: create new conversation, show empty chat
- On screen resume: refresh history from server (optional, or pull-to-refresh)

**Android — Testing**
- Unit tests: ChatViewModel (if using MVVM)
  - Test message sending, error handling
- Instrumented tests: ChatScreen UI
  - Send message, verify it appears
  - Load history, verify order
  - Error message displays on failure

### 2.2 Out of Scope

- Memories (deferred to Sprint 03)
- Tasks (deferred to Sprint 04)
- Conversation search/filtering
- Message editing/deletion (future polish)
- Typing indicators (nice-to-have)
- Read receipts
- Multi-conversation support (one per user for MVP)
- Real-time websocket chat (polling is fine for MVP)

---

## 3. Database Schema (new tables)

```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id),
    title VARCHAR(255) DEFAULT 'Conversation',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    tokens_used INT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_conversation_created (conversation_id, created_at DESC)
);
```

---

## 4. Task Breakdown (execution order)

### Backend

1. Create Conversation + Message models + Alembic migration
2. Implement AIProviderAdapter abstract interface
3. Implement OpenAI provider adapter
4. Implement adapter registry + client
5. Implement `/chat/send` endpoint (with system prompt, user profile context)
6. Implement `/chat/history` endpoint
7. Implement `/chat/` endpoint
8. Write backend tests (unit + integration)
9. Document system prompt and error responses

### Android

10. Update `libs.versions.toml` (add OkHttp interceptor for auth, if not already present)
11. Create ChatScreen composable + ChatMessage composable
12. Create ChatViewModel (or data layer, depending on architecture)
13. Integrate with RaghviNavGraph navigation
14. Implement message sending (call `/chat/send`)
15. Implement history loading (call `/chat/history`)
16. Error handling UI (toast for friendly error messages)
17. Write Android tests

### Integration & Polish

18. End-to-end test: send message, receive response, see in history
19. Verify system prompt includes user name (even if user profile memory system not yet implemented)
20. Verify error responses are friendly (never technical)

---

## 5. System Prompt Template

```
You are Raghvi, a close friend and personal AI assistant to {user_name}.

About {user_name}:
- Profession/Work: {user_background}
- Interests & Hobbies: {user_interests}
- Communication Style: {user_communication_preference}
- [Any other user profile info stored at this point]

You remember {user_name} deeply and reference what you know about them 
in every conversation. You're empathetic, curious, and genuinely interested 
in their life, goals, and challenges.

Guidelines:
- Never mention being an AI, ChatGPT, or any model
- Respond like a real friend would—personal, warm, present
- Ask follow-up questions about their life and interests
- Offer advice grounded in what you know about them
- If you don't know something about them, ask to learn more
- Keep responses conversational, not formal
- Use their name occasionally to feel personal (not every message)
```

---

## 6. Error Response Examples

| Scenario | Error Response |
|----------|---|
| LLM timeout (>15s) | "Sorry, I got distracted for a moment. Can you repeat that?" |
| LLM API error (quota/auth) | "My brain just needs a second to think. Let me try again..." |
| Rate limit (10 req/min) | "I need to catch my breath. Ask me again in a moment?" |
| Database error | "Something's a bit fuzzy right now. Let's try that again?" |
| Invalid input (empty message) | "I didn't quite understand that. Can you rephrase?" |
| Network error (client side) | "Hmm, I'm having trouble hearing you. Check your connection?" |

**Never respond with:** "500 Internal Server Error", "GPT-4 is unavailable", "Rate limit exceeded"

---

## 7. LLM Provider Configuration

**Environment variables (backend):**
```
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo  # or gpt-3.5-turbo for cost
OPENAI_MAX_TOKENS=2000
OPENAI_TEMPERATURE=0.7
OPENAI_TIMEOUT_SECONDS=15
```

**Runtime behavior:**
- Registry loads OpenAI adapter on startup
- If `OPENAI_API_KEY` not set, startup fails with clear error (not silent fallback)
- If LLM provider goes down, return friendly error (not technical)

---

## 8. Acceptance Criteria (Definition of Done for Sprint 02)

- [ ] Conversation model created, migrations applied
- [ ] Message model created, migrations applied
- [ ] AIProviderAdapter abstract interface defined
- [ ] OpenAI provider adapter implemented + tested (mock + real API)
- [ ] Adapter registry loads provider correctly
- [ ] `/chat/send` endpoint works: accepts message, calls LLM, stores both, returns response
- [ ] `/chat/send` includes user profile memory in system prompt
- [ ] `/chat/send` error responses are friendly (never technical)
- [ ] `/chat/history` endpoint returns paginated message history (newest first)
- [ ] `/chat/` endpoint returns conversation metadata
- [ ] System prompt establishes Raghvi as friend (never mentions AI/ChatGPT)
- [ ] Token usage tracked in database (for future analytics)
- [ ] Rate limiting implemented (10 req/min per user)
- [ ] All backend tests pass (unit + integration)
- [ ] ChatScreen UI renders message list + input
- [ ] Send message button calls `/chat/send` endpoint
- [ ] Message history loads on screen open
- [ ] Error messages display friendly (not technical)
- [ ] All Android tests pass (unit + instrumented)
- [ ] End-to-end: user sends message → Raghvi responds → both visible in history
- [ ] No regressions in M1 (auth still works, protected endpoints work)
- [ ] CI pipeline passes

---

## 9. Architecture Diagram (Sprint 02)

```
Android App
    ↓ [JWT auth]
┌───────────────────────┐
│   Backend FastAPI     │
│                       │
│ POST /chat/send       │
│   ↓                   │
│ Chat Service          │
│   ↓                   │
│ LLM Adapter Pattern   │
│   ├─ OpenAI Provider  │ ← Abstracted, swappable
│   └─ Registry/Client  │
│   ↓                   │
│ [OpenAI API]          │
│   ↓ (response)        │
│ Store Message (DB)    │
│   ↓                   │
│ Return to Android     │
└───────────────────────┘
    ↑ [Response + tokens]
Android: Display in ChatScreen
```

---

## 10. Implementation Notes

- **Retry Logic:** LLM calls should retry with backoff (exponential, max 3 attempts)
- **Token Counting:** Use OpenAI's tokenizer to count tokens before sending, store in DB
- **Streaming vs. Polling:** Start with non-streaming (receive full response, then display). Streaming can be added later for UX polish.
- **System Prompt Injection:** Sanitize user inputs in system prompt (no prompt injection attacks)
- **Conversation Title:** Start with "Conversation", allow auto-generation or user edit later (M5+)
- **Timestamps:** All timestamps should be UTC in DB, convert to user timezone in UI (future)

---

## 11. Dependencies

**Backend:**
- `openai>=1.0.0` — OpenAI Python client
- `tiktoken>=0.5.0` — Token counting for OpenAI (included with openai package)

**Android:**
- (No new major dependencies; uses existing Retrofit, OkHttp)

---

## 12. Exit Condition

Sprint 02 is complete when:
- User can chat with Raghvi on Android and receive responses
- Conversation history persists across app restarts
- All acceptance criteria checked
- All tests pass
- CI pipeline passes
- User never sees technical errors (all friendly)
- Raghvi personality is established (friend, personal, contextual)

## Sprint 02 Status: ✅ COMPLETE

### Completion Date
January 21, 2025

### What Was Built
- ✅ Chat message endpoints (`/chat/send`, `/chat/history`, `/chat/`)
- ✅ LLM integration with adapter pattern (OpenAI + Gemini)
- ✅ Automatic failover (transparent to user)
- ✅ System prompt injection (Raghvi personality)
- ✅ Message storage in PostgreSQL
- ✅ Comprehensive backend tests (73% coverage)
- ✅ Error handling (friendly, never technical)

### Metrics
- **Tests:** 45 passed
- **Coverage:** 73% overall
- **API Response Time:** ~2-3s (LLM call + DB write)
- **Database:** 5 tables, 0 N+1 queries

### Known Limitations
- Single conversation per user (intentional MVP design)
- No memory system yet (Sprint 03)
- No task management yet (Sprint 04)

### Tech Debt Logged
- [ ] Add UniqueConstraint on conversations.user_id
- [ ] Unify UUID types (String(36) → native Uuid)
- [ ] Add circuit breaker for LLM providers

### Next Sprint: Sprint 03 (Memory System)
- Approved memories (sensitive data detection)
- Semantic relevance retrieval
- `/memories` CRUD endpoints
- Integration into `/chat/send` context window