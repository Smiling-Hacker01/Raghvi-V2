# Sprint 03 — Memory System

**Milestone:** M2 (Chat, Memory, Tasks)  
**Sprint Goal:** Users can save memories, Raghvi uses them for context. Sensitive data gets explicit approval before storage.

---

## 1. Objective

By the end of this sprint:

- Users can save memories from chat or explicitly
- Normal memories auto-approve instantly (no friction)
- Sensitive memories (passwords, card numbers, PINs) require explicit approval
- Memories are encrypted at rest (sensitive data)
- Raghvi retrieves semantically-relevant memories for each conversation turn
- User always sees Raghvi as contextually aware of their life
- Memories improve response quality without user noticing the mechanism

---

## 2. Scope

### 2.1 In Scope

**Backend — Database & Models**
- `Memory` model: `id`, `user_id`, `content`, `is_sensitive`, `approved_at`, `created_at`, `updated_at`, `deleted_at`
- Alembic migration for Memory table + indexes
- Sensitive data classification (pattern detection)

**Backend — Sensitive Data Detection**
- `app/services/security/sensitive_detector.py`
  - Patterns: credit card numbers (16 digits), SSN (xxx-xx-xxxx), passwords (common patterns)
  - Keywords: "password", "pin", "secret", "key", "token", "card number", "cvv"
  - Patterns for bank account, routing numbers
  - Returns: `is_sensitive: bool`, `reason: str` (e.g., "Contains credit card number")
- If detected, flag memory as sensitive + require approval

**Backend — Memory Encryption**
- Sensitive memories encrypted at rest (AES-256)
- Use SQLAlchemy hybrid property: `content` stored encrypted in DB, decrypted on retrieval
- Key management: stored in environment (for MVP), KMS in production (M5+)
- Non-sensitive memories stored plaintext (no performance hit)

**Backend — Memory Endpoints**
- `POST /memories` — create memory (auto-approve if normal, require approval if sensitive)
  - Request: `{"content": "user provided text"}`
  - Response: `{"id": "...", "is_sensitive": true/false, "status": "approved"/"pending_approval"}`
- `GET /memories` — list user's memories (paginated, filters: all, approved, pending, deleted)
  - Query: `limit=20&offset=0&filter=approved`
  - Response: `{"memories": [...], "total": 42, "pending_count": 2}`
- `PATCH /memories/{id}/approve` — approve a pending sensitive memory
  - Request: `{"confirm": true}`
  - Response: `{"id": "...", "status": "approved"}`
- `PATCH /memories/{id}/reject` — reject a pending memory (soft delete)
  - Response: `{"id": "...", "status": "rejected"}`
- `DELETE /memories/{id}` — hard delete (user requests removal)
  - Response: `204 No Content`

**Backend — Memory Retrieval for Chat**
- `get_memories_for_context(user_id, current_message_content, limit=9) -> List[Memory]`
  - Semantic relevance (not just recency): compare current message topic to memory content
  - Simple approach (MVP): TF-IDF or keyword overlap for relevance
  - Return top 9 most relevant approved memories
  - Called before every LLM call in `/chat/send`
- Memory context included in system prompt alongside user profile memory
- Modify system prompt to reference memories: "You remember: [memory1], [memory2], ..."

**Backend — Memory-Enhanced Chat**
- Modify `/chat/send` to:
  1. Retrieve user profile memory (always included)
  2. Retrieve 9 semantically-relevant memories
  3. Build system prompt with user profile + memories
  4. Send to LLM with last 20 messages
  5. Store message as before
- Track which memories were used in response (for analytics/recommendations later)

**Backend — Testing**
- Unit tests: sensitive data detector (false positives, false negatives)
- Unit tests: memory encryption/decryption
- Integration tests: `/memories` CRUD endpoints
  - Create normal memory, verify auto-approved
  - Create sensitive memory, verify pending approval
  - Approve/reject sensitive memory
  - List memories with filters
- Integration tests: memory retrieval for context
  - Verify semantic relevance scoring
  - Verify top-9 selection
- Integration tests: chat with memories
  - Send message, verify memories included in LLM prompt

**Android — Memories Screen**
- `MemoriesScreen.kt` — tab in main app
  - List all user memories (paginated)
  - Filter tabs: "All", "Approved", "Pending"
  - Each memory shows: content, approval status, creation date
  - Tap memory to view details, approve/reject/delete
- `MemoryCard.kt` — composable for individual memory
  - Display content (truncated if long)
  - Status badge (Approved/Pending)
  - Action buttons (Approve, Reject, Delete)
  - Long-press for more options

**Android — In-Chat Memory Suggestions (optional for Sprint 03, can defer to M5+)**
- After Raghvi response, offer "Save as memory?" button/prompt
- If user taps: create memory directly without opening Memories screen
- Keep UX frictionless (one tap)

**Android — Memory Approval UI**
- If sensitive memory pending: notification or badge in Memories tab
- Tap to approve/reject
- Biometric auth gate (optional: require biometric to approve sensitive memories)

**Android — Testing**
- Unit tests: memory CRUD (create, list, approve, delete)
- Instrumented tests: MemoriesScreen UI
  - Create memory through chat
  - Navigate to Memories tab
  - See pending sensitive memory
  - Approve it
  - Verify it moves to approved list

### 2.2 Out of Scope

- Memory search/full-text search (M5+)
- Memory graph/relationships (M5+)
- Memory embeddings/semantic search (M5+, MVP uses simple keyword matching)
- Memory sharing/collaboration
- Memory export/backup
- Memory auto-deletion after time period (M3+)
- Biometric gate on memory approval (nice-to-have, can be added after)

---

## 3. Database Schema (new tables)

```sql
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,  -- encrypted if is_sensitive=true
    is_sensitive BOOLEAN DEFAULT false,
    approved_at TIMESTAMP,  -- NULL if pending or rejected
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP,  -- soft delete
    INDEX idx_user_approved (user_id, approved_at) WHERE deleted_at IS NULL
);

-- Optional: track memory usage for analytics
CREATE TABLE memory_usage_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id),
    memory_id UUID NOT NULL REFERENCES memories(id),
    used_in_response BOOLEAN DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

## 4. Task Breakdown (execution order)

### Backend

1. Create Memory model + Alembic migration
2. Implement sensitive data detector (patterns + keywords)
3. Implement memory encryption/decryption (SQLAlchemy hybrid property)
4. Implement `/memories` CRUD endpoints
5. Implement memory retrieval + semantic relevance scoring
6. Modify `/chat/send` to include memories in system prompt
7. Write backend tests (unit + integration)
8. Document sensitive data patterns and encryption strategy

### Android

9. Create MemoriesScreen + MemoryCard composables
10. Implement memory CRUD calls (integrate with API)
11. Add "Save as memory" button in ChatScreen (optional)
12. Add memory approval UI
13. Write Android tests

### Integration

14. End-to-end test: save memory in chat → verify in Memories screen → verify approved
15. End-to-end test: save sensitive data → verify pending approval → approve → use in next chat
16. Verify semantic relevance (send message, check which memories were retrieved)

---

## 5. Sensitive Data Detection Patterns

```python
SENSITIVE_PATTERNS = {
    'credit_card': r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b',
    'ssn': r'\b\d{3}[\s\-]?\d{2}[\s\-]?\d{4}\b',
    'password': r'(?i)(password|pwd|pass)\s*[:=]\s*\S+',
    'api_key': r'(?i)(api[_\-]?key|apikey)\s*[:=]\s*\S+',
    'bank_account': r'\b\d{8,17}\b',  # generic account numbers
}

SENSITIVE_KEYWORDS = [
    'password', 'pwd', 'pin', 'secret', 'token', 'key',
    'credit card', 'cvv', 'ssn', 'social security',
    'bank account', 'routing number', 'api key',
    'private key', 'passphrase', 'seed phrase'
]

# If content matches any pattern OR contains sensitive keywords, flag as sensitive
```

---

## 6. Memory Context in System Prompt

**System prompt modification:**

```
You are Raghvi, a close friend and personal AI assistant to {user_name}.

About {user_name}:
[User profile memory - from Sprint 02]

Things you remember about {user_name}:
- {memory_1}
- {memory_2}
- ... (up to 9 most relevant memories)

Use these memories to personalize your responses and show that you genuinely 
remember their life, interests, and context. Reference them naturally in conversation.
```

---

## 7. Semantic Relevance Scoring (MVP simple approach)

```python
# Simple TF-IDF / keyword overlap
def score_relevance(memory_content: str, current_message: str) -> float:
    # Extract keywords from both
    memory_words = set(memory_content.lower().split())
    message_words = set(current_message.lower().split())
    
    # Overlap ratio (Jaccard similarity)
    intersection = memory_words & message_words
    union = memory_words | message_words
    similarity = len(intersection) / len(union) if union else 0
    
    return similarity

# Get top 9 approved memories ranked by relevance
relevant_memories = sorted(
    [m for m in user_memories if m.approved_at],
    key=lambda m: score_relevance(m.content, current_message),
    reverse=True
)[:9]
```

**Future (M5+):** Replace with embedding-based semantic search (higher accuracy).

---

## 8. Encryption Example (for documentation)

```python
# Hybrid property approach
from sqlalchemy.ext.hybrid import hybrid_property

class Memory(Base):
    __tablename__ = "memories"
    
    _content_encrypted = Column(String, name="content")
    
    @hybrid_property
    def content(self):
        if not self._content_encrypted:
            return None
        return decrypt(self._content_encrypted, settings.encryption_key)
    
    @content.setter
    def content(self, value):
        if value:
            self._content_encrypted = encrypt(value, settings.encryption_key)
```

---

## 9. Acceptance Criteria (Definition of Done for Sprint 03)

- [ ] Memory model created, migrations applied
- [ ] Sensitive data detector implemented (patterns + keywords)
- [ ] Sensitive data detection has low false positives (<5%)
- [ ] Memory encryption implemented (SQLAlchemy hybrid)
- [ ] Normal memories auto-approve on creation
- [ ] Sensitive memories require explicit user approval
- [ ] `/memories` CRUD endpoints work (create, list, approve, reject, delete)
- [ ] Memory retrieval returns 9 semantically-relevant memories
- [ ] System prompt includes user profile + 9 memories
- [ ] `/chat/send` uses memories in LLM context
- [ ] MemoriesScreen displays all memories with filters
- [ ] "Save as memory" works in ChatScreen (optional if added)
- [ ] Memory approval UI works (approve/reject sensitive memory)
- [ ] All backend tests pass
- [ ] All Android tests pass
- [ ] End-to-end: save normal memory → auto-approved → used in next chat
- [ ] End-to-end: save sensitive memory → pending → approve → used in next chat
- [ ] No regressions in Chat (Sprint 02) or Auth (M1)
- [ ] CI pipeline passes

---

## 10. Example Conversation with Memories

```
User: "I've been thinking about learning guitar"
[System stores as memory (normal info)]

Raghvi: "That's awesome! Are you interested in any particular genre?"

---

User: "My password for work is SuperSecureP@ss123"
[System detects sensitive pattern → flags as sensitive, requires approval]
[UI shows: "This looks like sensitive data. Approve to save?"]

User: [Approves]
[Memory stored encrypted]

Raghvi: "Got it, I've securely saved that for you."

---

User: "How should I practice guitar if I have limited time?"
[System retrieves memories: includes "interested in guitar", "limited time", user profile]

Raghvi: "Since you want to learn guitar but have limited time, 
here's what worked for others in your situation..."
[Response is personalized because memories were included]
```

---

## 11. Exit Condition

Sprint 03 is complete when:
- Memories are stored and retrieved correctly
- Sensitive data is detected and requires approval
- Raghvi personalizes responses using memories
- All tests pass
- CI pipeline passes
- User sees Raghvi as genuinely remembering them