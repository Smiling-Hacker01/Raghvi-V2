# M2 — Chat, Memory, and Tasks Foundation

**Milestone:** M2 — Chat, Memory, and Tasks Foundation  
**Duration:** ~3 sprints (Sprint 02, 03, 04)  
**Milestone Goal:** Enable users to chat with Raghvi, manage memories, and create tasks/reminders.

---

## 1. M2 Vision & Scope

By the end of M2, users can:

- **Chat with Raghvi** — send messages, receive AI-generated responses, maintain conversation history
- **Manage memories** — save important context, approve/edit/delete memories, retrieve them in future conversations
- **Create tasks & reminders** — create tasks, set due dates, receive reminder notifications (optional in M2)
- **Persistent context** — Raghvi remembers approved memories across sessions and uses them to personalize responses

**M2 does NOT include:**
- Proactive daily briefings (M3)
- Safe Android device actions (M4)
- Voice assistant (future)
- Advanced memory features like graph/RAG (future)
- Multi-user collaboration (future)

---

## 2. Technology Decisions

### **AI/LLM Integration — Adapter/Plugin Architecture**

**Decision: Adapter/Plugin pattern (no vendor lock-in, extensible)**

- Define `AIProviderAdapter` abstract interface
- Each LLM provider implements the adapter (send_message, validate_config, get_model_info)
- Plugin registry loads adapter based on `AI_PROVIDER` env config
- Start with **OpenAI's API** (most stable for MVP)
- Future: add Anthropic Claude, local models, etc. by creating new adapters (zero impact on chat/memory/task logic)

**Implementation:**
- `app/services/ai/adapter.py` — abstract `AIProviderAdapter` interface
- `app/services/ai/providers/openai.py` — OpenAI adapter
- `app/services/ai/providers/anthropic.py` — Anthropic adapter (template for future)
- `app/services/ai/registry.py` — plugin registry, loads adapter by name
- `app/services/ai/client.py` — client that uses registry, business logic only touches this

**Key: Zero coupling between chat/memory/task logic and LLM provider choice**

### **System Prompt & User Context**

**Decision: Raghvi is a friend, never a generic AI**

- System prompt establishes Raghvi's personality and relationship with user
- **User profile memory always included** in every LLM call (name, background, preferences)
- Raghvi never mentions being an AI, never acts like ChatGPT
- Responses are personal, empathetic, and grounded in knowledge of the user
- User should never feel abandoned or forgotten mid-conversation

**System Prompt Template:**
```
You are Raghvi, a close friend and personal AI assistant to [User Name].
You remember [User Name] deeply and reference what you know about them 
in every conversation. You're empathetic, curious, and genuinely interested 
in their life and goals.

About [User Name]: [User profile memory - work, interests, family, communication style]

You never mention being an AI, ChatGPT, or any model. You respond like a 
real friend would—personal, warm, and fully present in the conversation.
```

### **Memory System — Sensitive Data Handling**

**Decision: Auto-approve normal info, explicit approval for sensitive data**

- **Normal memories** (work, hobbies, family, interests, preferences) → auto-approve immediately
- **Sensitive memories** (passwords, credit card numbers, SSNs, PINs, secrets) → flag, require explicit user approval, encrypt at rest
- Sensitive data detection: pattern matching on keywords + user warning
- All memories improve future responses

**Implementation:**
- Sensitive data detector in memory creation
- If sensitive: require user confirmation before storing
- Store sensitive data encrypted (AES via db-level encryption or app-level)
- Audit log: track which sensitive memories were accessed when

### **Context Window & Memory Retrieval**

**Decision: Last 20 messages + semantically-relevant memories (not just recent)**

- Send LLM: last 20 messages from conversation + top 10 memories
- **Top 10 always includes:** user profile memory (critical for context continuity)
- **Remaining 9:** semantically relevant to current conversation topic (not just most recent)
- Why: Ensures Raghvi never forgets the user, can personalize responses, maintains emotional connection

**Implementation:**
- `get_memories_for_context(user_id, current_topic, limit=9)` — retrieve semantically-relevant memories
- User profile memory loaded separately, always included
- Combined into system prompt for every LLM call

### **Conversation Storage**

**Decision: Store full conversation history in DB**

- `Conversation` table: one per user, metadata (created_at, updated_at, title)
- `Message` table: one per message (user text + Raghvi response), timestamps
- Why: enables re-reading history, context retrieval for memory, analytics later
- Not: streaming or ephemeral (we store everything)

### **Memory System Architecture**

**Decision: Simple approval-based memory, no graph/RAG yet**

- User can highlight/save statements as memories
- Memories require explicit user approval before storing
- On each chat turn: retrieve last N approved memories relevant to the conversation
- Raghvi includes memories in system prompt: "User has previously told you: [memories]"
- No semantic search/embeddings yet (M5+), just recency-based retrieval for MVP

**Implementation:**
- `Memory` table: user_id, text, approved_at, created_at
- `get_memories_for_context()` — returns N most recent approved memories
- Memories are optional (user doesn't have to save any)

### **Tasks/Reminders**

**Decision: Tasks stored, reminders deferred to M3**

- `Task` table: user_id, title, description, due_date, completed_at, created_at
- Full CRUD on tasks (create, read, update, delete)
- Status: open, completed, deleted (soft delete)
- Reminders (notifications) — **deferred to M3** (requires push notifications setup, complex on Android)
- M2: tasks exist but no notifications yet

### **Error Responses — Stay in Character**

**Decision: Friendly, human-like error messages (never break Raghvi character)**

- LLM timeout (>15s) → "Sorry, I got distracted for a moment. Can you repeat that?"
- LLM error (API down) → "My brain just needs a second to think. Let me try again..."
- Rate limit (10 req/min exceeded) → "I need to catch my breath. Ask me again in a moment?"
- Database error → "Something's a bit fuzzy right now. Let's try that again?"
- Invalid input → "I didn't quite understand that. Can you rephrase?"

**Never respond with:**
- "500 Internal Server Error"
- "API rate limit exceeded"
- "GPT-4 is unavailable"
- Technical jargon or stack traces

**Why:** User sees Raghvi as a friend, not a service. Errors should feel like a momentary lapse of focus, not a system failure.

---

## 3. Database Schema (new tables for M2)

```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL FOREIGN KEY REFERENCES users(id),
    title VARCHAR(255),
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    UNIQUE(user_id)  -- one conversation per user for MVP
);

CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL FOREIGN KEY REFERENCES conversations(id),
    role VARCHAR(10) NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    tokens_used INT,  -- track LLM token usage
    INDEX(conversation_id)
);

CREATE TABLE memories (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL FOREIGN KEY REFERENCES users(id),
    content TEXT NOT NULL,
    approved_at TIMESTAMP,  -- NULL if not yet approved
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP,  -- soft delete
    INDEX(user_id, approved_at)
);

CREATE TABLE tasks (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL FOREIGN KEY REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    due_date DATE,
    completed_at TIMESTAMP,  -- NULL if not completed
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP,  -- soft delete
    INDEX(user_id, due_date)
);
```

---

## 4. Sprint Breakdown

### **Sprint 02 — Basic Chat & Message History**

**Goal:** Users can chat with Raghvi and see message history.

**Backend:**
- Conversation model + migrations
- Message model + migrations
- `POST /chat/send` — accept user message, call LLM, store both, return response
- `GET /chat/history` — return conversation history (paginated)
- `GET /chat/` — get current conversation metadata
- LLM service abstraction (OpenAI provider first)
- System prompt that establishes Raghvi's personality
- Error handling (LLM timeout, API errors, etc.)

**Android:**
- Chat screen UI (message list + input field)
- Send message button → call `/chat/send` endpoint
- Display response in UI
- Scroll to latest message on new response
- Show loading indicator while waiting for response

**Tests:**
- Unit tests for LLM service interface
- Integration tests for `/chat/send` (mocked LLM)
- Integration tests for `/chat/history` (pagination, ordering)
- Android UI tests for message display

**Exit Criteria:**
- User can type a message and receive a Raghvi response
- Message history is preserved (reload app, see old messages)
- Responses handle timeout/error gracefully

---

### **Sprint 03 — Memory System**

**Goal:** Users can save memories, approve them, and Raghvi uses them in responses.

**Backend:**
- Memory model + migrations
- `POST /memories` — create memory (auto-unapproved)
- `GET /memories` — list user's memories (approved + unapproved)
- `PATCH /memories/{id}/approve` — approve a memory
- `DELETE /memories/{id}` — soft-delete memory
- Modify `/chat/send` to:
  - Retrieve approved memories before calling LLM
  - Include memories in system prompt
  - Store which memories were used in this response (for analytics later)

**Android:**
- Memory suggestion UI (appear after Raghvi response, or on-demand)
- "Save as memory" button in chat
- Show dialog for user to confirm/edit before saving
- Memories tab — view all memories (approved/unapproved), approve, delete
- Biometric auth gate on memories (optional for M2, nice-to-have)

**Tests:**
- Integration tests for memory CRUD
- Integration tests for `/chat/send` with memories in context
- Verify memories are included in LLM prompt
- Android UI tests for memory approval flow

**Exit Criteria:**
- User can save a memory from chat
- User can approve/reject memories
- Raghvi references approved memories in responses
- Memory retrieval is fast (<100ms, not LLM call time)

---

### **Sprint 04 — Tasks & Reminders (Tasks Only)**

**Goal:** Users can create, read, update, delete tasks. Reminders deferred to M3.

**Backend:**
- Task model + migrations
- `POST /tasks` — create task
- `GET /tasks` — list tasks (with filters: open, completed, overdue)
- `PATCH /tasks/{id}` — update task (title, description, due_date, mark complete)
- `DELETE /tasks/{id}` — soft-delete task
- Optional: Extract task intent from chat
  - If Raghvi detects task creation in chat (e.g., "remind me to buy milk"), offer to save as task
  - Not required for M2, but nice-to-have polish

**Android:**
- Tasks tab/screen (list all tasks)
- Create task form (title, description, due date)
- Mark task complete (checkbox)
- Edit task (tap to modify)
- Delete task (swipe or button)
- Task filters: all, open, completed

**Tests:**
- Integration tests for task CRUD
- Integration tests for task filtering
- Android UI tests for task creation/completion flow

**Exit Criteria:**
- User can create, list, complete, and delete tasks
- Tasks persist across sessions
- Task due dates display and sort correctly

---

## 5. Architecture Diagram (Logical)

```
┌─────────────────────────────────────────────────────────────┐
│                      Android App                            │
│  ┌──────────┐  ┌─────────┐  ┌────────┐  ┌──────────┐       │
│  │   Chat   │  │ Memories│  │ Tasks  │  │ Profile  │       │
│  └────┬─────┘  └────┬────┘  └───┬────┘  └────┬─────┘       │
│       │             │            │            │             │
│  ┌────┴─────────────┴────────────┴────────────┴────┐        │
│  │        API Client (Retrofit + Interceptor)      │        │
│  │   - Attaches JWT access token to all requests   │        │
│  │   - Handles 401 refresh-and-retry               │        │
│  └─────────────────────┬──────────────────────────┘        │
└────────────────────────┼──────────────────────────────────────┘
                         │ HTTP/HTTPS
         ┌───────────────┼────────────────┐
         │               │                │
    ┌────▼────┐    ┌─────▼────┐    ┌────▼────────┐
    │ /auth/* │    │ /chat/*   │    │ /tasks/*,   │
    │         │    │ /memories │    │ /memories   │
    └────┬────┘    │ /*        │    └────┬────────┘
         │         └─────┬─────┘         │
         │               │               │
         │ ┌─────────────┴───────────────┤
         │ │                             │
    ┌────▼─┴────────────┐    ┌──────────▼──────┐
    │  FastAPI Backend  │    │   LLM Service   │
    │  (Auth, Chat,     │    │   (OpenAI API)  │
    │   Memory, Tasks)  │    │                 │
    └────┬──────────────┘    └─────────────────┘
         │
    ┌────▼──────────────┐
    │   PostgreSQL      │
    │  (Users, Chats,   │
    │   Memories,       │
    │   Tasks, Tokens)  │
    └───────────────────┘
```

---

## 6. Integration Points with M1 (Auth)

- All M2 endpoints require valid JWT access token (protected via middleware from M1)
- User context extracted from token (user_id used for all queries)
- Refresh token logic unchanged (still 14-day expiry, rotation on use)
- Logout clears conversation/memory data on client (optional, not on server)

---

## 7. Known Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| LLM API cost spiraling | Rate limit requests per user (e.g., 10 req/min), log token usage, alert on anomalies |
| LLM timeout/failure | Graceful error handling, retry with backoff, fallback response ("I'm having trouble thinking right now") |
| Conversation context too large | Cap context window: last 20 messages + 10 memories, not entire history |
| Memory explosion (user saves 1000 memories) | Paginate memory list, lazy-load, soft-delete stale memories after 1 year (M3+) |
| Task due date in past | Highlight overdue tasks in UI, allow manual reschedule |
| Concurrent chat messages | Queue messages, process sequentially per user (prevent race conditions) |

---

## 8. Out of Scope (explicitly deferred)

- **Reminders/Notifications** — M3 (requires push notification setup on Android)
- **Memory search/embeddings** — M5+ (semantic search, RAG)
- **Advanced LLM features** — M5+ (function calling, tool use)
- **Multi-turn task workflow** — M3+ (task dependencies, subtasks)
- **Conversation sharing** — M5+ (export, share with others)
- **Offline mode** — Future (requires local storage sync)
- **Real-time collaboration** — Enterprise feature (future)

---

## 9. M2 Success Criteria

- [ ] Users can send messages to Raghvi and receive responses
- [ ] Conversation history persists across sessions
- [ ] Users can save and approve memories
- [ ] Raghvi includes approved memories in responses
- [ ] Users can create, read, update, delete tasks
- [ ] All endpoints are protected (require valid JWT)
- [ ] All backend tests pass (chat, memory, task endpoints)
- [ ] All Android UI tests pass
- [ ] CI pipeline passes
- [ ] No regressions in M1 auth functionality
- [ ] Root README updated with chat/memory/task endpoint documentation

---

## 10. Timeline & Resource Estimates

| Sprint | Focus | Backend | Android | Tests | Estimated Days |
|--------|-------|---------|---------|-------|-----------------|
| 02 | Chat | 5–6 | 4–5 | 2–3 | 12–15 |
| 03 | Memory | 3–4 | 3–4 | 2–3 | 10–13 |
| 04 | Tasks | 3–4 | 3–4 | 2–3 | 10–13 |
| **Total M2** | | | | | **32–41 days** |

(Assumes solo developer, full-time, no blockers)

---

## 11. Decision Checklist (All Locked ✅)

- [x] **LLM Provider:** Adapter/plugin pattern, start with OpenAI, extensible for future
- [x] **Conversation Model:** One per user (not per topic) for MVP
- [x] **Memory Approval:** Auto-approve normal info; explicit approval for sensitive data only (passwords, cards, PINs)
- [x] **Context Window:** Last 20 messages + 10 semantically-relevant memories (always includes user profile memory)
- [x] **Raghvi Personality:** Friend, never mentions being AI, always contextual, never forgets user
- [x] **Task Reminders:** Deferred to M3 (no push notifications in M2)
- [x] **Rate Limiting:** 10 req/min per user
- [x] **Error Handling:** Friendly, human-like responses (stay in character, never technical errors)

---

## 12. Next Steps After M2 Approval

1. Review this document and confirm all decisions
2. Create individual sprint plans (`sprint-02-chat.md`, `sprint-03-memory.md`, `sprint-04-tasks.md`)
3. Start implementation once approved

---

## Appendix: Example Conversation Flow

```
User: "Hi Raghvi, my name is Alice and I work as a software engineer."
[Saves as memory if user approves]

Raghvi: "Nice to meet you, Alice! I'm Raghvi, your personal AI assistant. 
I'll remember that you're a software engineer so I can give you more relevant advice."

User: "What's a good way to debug async code in Python?"
[Raghvi includes memory: "Alice is a software engineer" in LLM context]

Raghvi: "Since you work with software engineering, here are some Python-specific async debugging tips..."
[Response tailored by knowledge of Alice's background]

User: "Create a task: Review the async code pattern by Friday"
[Optional: Extract task intent from chat, create task]

Raghvi: "I've created a task 'Review the async code pattern' due Friday. 
Good idea to set a deadline for yourself!"
```

---

## Document Complete

This M2 plan is locked in and ready for sprint planning. All technology decisions are made, risks identified, and exit criteria defined.

**Ready to proceed to Sprint 02 detailed planning?**