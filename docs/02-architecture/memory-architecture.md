# Memory Architecture

## Overview

Raghvi implements a **Hybrid Layered Memory Architecture** (per ADR-001) with five memory layers, sensitivity classification, TF-IDF semantic retrieval, and LLM-based auto-extraction.

---

## Memory Layers

| Layer | Purpose | Persistence | Retrieval |
|-------|---------|-------------|-----------|
| **Working Memory** | Current conversation context (last 15-20 messages) | Session-only | Always included in LLM context |
| **Conversation History** | Full message log | Permanent (until user deletes) | Paginated via `/chat/history` |
| **Episodic Memory** | Meaningful events, milestones | Permanent | Not yet implemented (MVP) |
| **Semantic Memory** | Stable facts, preferences, goals | Permanent with lifecycle | TF-IDF retrieval (top-9 per turn) |
| **Project Memory** | Project-specific context | Active project duration | Not yet implemented (MVP) |

**Current MVP**: Working Memory + Conversation History + Semantic Memory

---

## Memory Model

```python
class Memory(Base):
    __tablename__ = "memories"
    
    id = Column(Uuid, primary_key=True, default=uuid4)
    user_id = Column(String(36), nullable=False, index=True)
    content = Column(Text, nullable=False)          # Encrypted if is_sensitive + is_encrypted
    is_sensitive = Column(Boolean, default=False)   # PUBLIC/SENSITIVE/CRITICAL
    is_encrypted = Column(Boolean, default=False)   # AES-256-GCM for CRITICAL
    approved_at = Column(DateTime, nullable=True)   # NULL = pending, datetime = approved
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)
    deleted_at = Column(DateTime, nullable=True)    # Soft delete
```

**Location**: `backend/app/models/memory.py`

---

## Sensitivity Classification

### Detection Engine

```python
class SensitivityEngine:
    def analyze(self, content: str) -> DetectionResult:
        # 1. Run pattern rules (regex for credit cards, SSN, passwords, API keys)
        # 2. Run keyword rules (password, pin, secret, token, cvv, etc.)
        # 3. Calculate weighted score
        # 4. Return severity: PUBLIC (<50), SENSITIVE (50-99), CRITICAL (≥100)
```

**Location**: `backend/app/services/memory/rules/engine.py`

### Classification Rules

| Severity | Score Range | Examples | Approval |
|----------|-------------|----------|----------|
| **PUBLIC** | < 50 | Preferences, hobbies, location, job, goals | Auto-approved |
| **SENSITIVE** | 50–99 | Email, phone, address, birthday | Pending user approval |
| **CRITICAL** | ≥ 100 | Passwords, credit cards, SSN, API keys, private keys | Never auto-approved, encrypted |

### Patterns Detected

```python
SENSITIVE_PATTERNS = {
    'credit_card': r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b',
    'ssn': r'\b\d{3}[\s\-]?\d{2}[\s\-]?\d{4}\b',
    'password': r'(?i)(password|pwd|pass)\s*[:=]\s*\S+',
    'api_key': r'(?i)(api[_\-]?key|apikey)\s*[:=]\s*\S+',
    'bank_account': r'\b\d{8,17}\b',
}
```

**Location**: `backend/app/services/memory/rules/patterns.py`

---

## Memory Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Capture   │────►│  Analyze    │────►│  Classify   │
│  Candidate  │     │  (LLM/Rule) │     │  (Score)    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌──────────────┐            │
                    │   Decision   │◄───────────┘
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌─────────┐  ┌───────────┐ ┌──────────┐
        │ PUBLIC  │  │ SENSITIVE │ │ CRITICAL │
        │ Auto-ap │  │  Pending  │ │ Encrypt  │
        │ proved  │  │  Approval │ │ + Flag   │
        └────┬────┘  └─────┬─────┘ └────┬─────┘
             │             │             │
             ▼             ▼             ▼
        ┌─────────────────────────────────────┐
        │         Store in PostgreSQL         │
        │  (approved_at set/NULL, encrypted?) │
        └─────────────────────────────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │    Retrieval (TF-IDF)   │
              │   Top-9 relevant/turn   │
              └─────────────────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │   LLM Context Window    │
              │  System prompt + memory │
              └─────────────────────────┘
```

---

## Memory Retrieval (TF-IDF)

### Algorithm

```python
class TFIDFRetriever:
    def retrieve(self, user_id, query, session, top_k=9):
        # 1. Get approved memories (limit 70 for perf)
        # 2. Tokenize query + all memories (stopword removal)
        # 3. Calculate TF (term frequency) per document
        # 4. Calculate IDF (inverse document frequency) global
        # 5. Score = Σ(query_tf × doc_tf × idf) for matching terms
        # 6. Return top-K with score > 0
```

**Location**: `backend/app/services/memory/retrieval.py`

### Performance Optimizations

- Limit candidate memories to 70 (reduced from 100)
- Stopword filtering (98 common English words)
- Case-insensitive matching
- Jaccard-style similarity with TF-IDF weighting

---

## Auto-Extraction (LLM-Based)

### Extraction Prompt

```python
_EXTRACTION_SYSTEM_PROMPT = """You are a personal fact extractor.
Rules:
- Only extract explicit personal facts about THEMSELVES
- Never infer, assume, or fabricate
- Each fact ≤ 10 words, third-person format
- Return ONLY valid JSON array of strings
- If NO facts, return exactly: []

Examples:
"I just moved to Bangalore for a new ML job at Flipkart!"
→ ["Lives in Bangalore", "Works in Machine Learning", "Works at Flipkart"]
"I love hiking and my dog Max comes with me."
→ ["Loves hiking", "Has a dog named Max"]"""
```

### Flow

```python
async def extract_and_save_memories(user_id, message, session):
    # 1. Call LLM with extraction prompt (temp=0.0, max_tokens=200)
    # 2. Parse JSON array from response (defensive parsing)
    # 3. Deduplicate against existing approved + pending memories
    # 4. For each new fact: MemoryService.create_memory()
    # 5. Return created memories
```

**Location**: `backend/app/services/memory/extractor.py`

### Key Properties

- **Non-blocking**: Runs as background task after response sent
- **Fault-tolerant**: Silent failure (empty list) never blocks chat
- **Deduplication**: Exact-match (case-insensitive) against existing memories
- **Cost-controlled**: Low temp, small token limit

---

## Encryption (CRITICAL Memories)

### Implementation

```python
class EncryptionService:
    def encrypt_to_storage(self, plaintext: str, password: str) -> str:
        # 1. Derive key from password (PBKDF2, 100k iterations)
        # 2. Generate random nonce (12 bytes)
        # 3. AES-256-GCM encrypt
        # 4. Return: base64(nonce + ciphertext + tag)
    
    def decrypt_from_storage(self, stored: str, password: str) -> str:
        # 1. Decode base64
        # 2. Extract nonce, ciphertext, tag
        # 3. Derive key from password
        # 4. AES-256-GCM decrypt
        # 5. Return plaintext
```

**Location**: `backend/app/services/memory/encryption.py`

### Key Management (MVP)

- Key derived from user-provided password at encryption time
- Password NOT stored — user must provide to decrypt
- Production: Replace with KMS (AWS KMS, HashiCorp Vault)

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/memories` | Create memory (auto-detects sensitivity) |
| GET | `/memories` | List approved memories (paginated) |
| GET | `/memories/pending` | List pending approval memories |
| POST | `/memories/{id}/approve` | Approve (`{"approved": true}`) or reject (`{"approved": false}`) |
| DELETE | `/memories/{id}` | Soft-delete approved memory |
| GET | `/memories/stats` | Counts: total, approved, pending, deleted |

---

## Integration with Chat

### Context Injection

```python
# In ChatService.send_message():
relevant_memories = await retriever.retrieve(user_id, user_message, session)
system_prompt = await build_system_prompt(
    user_memories=relevant_memories,
    user_tasks=active_tasks,
    session=session
)
# system_prompt includes:
# "Things you remember about {user_name}:\n- {memory_1}\n- {memory_2}\n..."
```

### Memory + Task Context

Both memories and active tasks retrieved in parallel and included in system prompt for holistic context.

---

## Testing

| Test | Coverage |
|------|----------|
| Sensitivity detection | Patterns, keywords, scoring, false positive/negative rates |
| Encryption | Round-trip encrypt/decrypt, wrong password failure |
| CRUD endpoints | Create (all severities), list, approve, reject, delete, stats |
| Retrieval | Relevance scoring, top-K selection, empty/no-match cases |
| Auto-extraction | LLM parsing, deduplication, silent failure |
| Chat integration | Memories included in prompt, retrieval timing |

---

## Related ADRs

- [ADR-001: Memory Strategy](../03-decisions/ADR-001-memory-strategy.md)
- [ADR-004: Data Storage & Retrieval](../03-decisions/ADR-004-data-storage-and-retrieval.md)
- [ADR-012: Data Retention & Lifecycle](../03-decisions/ADR-012-data-retention-deletion-export-and-life-cycle.md)