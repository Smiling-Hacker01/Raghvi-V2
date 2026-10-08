# Data Model

## Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│      User       │       │  Conversation   │       │    Message      │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │◄──────│ id (PK)         │◄──────│ id (PK)         │
│ username (UQ)   │       │ user_id (FK,UQ) │       │ conversation_id │
│ email (UQ)      │       │ title           │       │ (FK)            │
│ password_hash   │       │ created_at      │       │ role            │
│ name            │       │ updated_at      │       │ content         │
│ phone           │       └─────────────────┘       │ tokens_used     │
│ preferences     │                                 │ created_at      │
│ created_at      │                                 └─────────────────┘
│ updated_at      │
└─────────────────┘
        │
        │ 1:N
        ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  RefreshToken   │       │     Memory      │       │      Task       │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ user_id (FK)    │       │ user_id (FK)    │       │ user_id (FK)    │
│ token_hash      │       │ content         │       │ title           │
│ expires_at      │       │ is_sensitive    │       │ description     │
│ revoked_at      │       │ is_encrypted    │       │ priority        │
│ created_at      │       │ approved_at     │       │ due_date        │
└─────────────────┘       │ created_at      │       │ status          │
                          │ updated_at      │       │ tags            │
                          │ deleted_at      │       │ auto_extracted  │
                          └─────────────────┘       │ completed_at    │
                                    │              │ created_at      │
                                    │ 1:N          │ updated_at      │
                                    ▼              │ deleted_at      │
                          ┌─────────────────┐       └─────────────────┘
                          │   Reminder      │                   │
                          ├─────────────────┤                   │ 1:N
                          │ id (PK)         │                   ▼
                          │ task_id (FK)    │       ┌─────────────────┐
                          │ user_id (FK)    │       │   Subscription  │
                          │ reminder_time   │       ├─────────────────┤
                          │ reminder_type   │       │ id (PK)         │
                          │ sent            │       │ user_id (FK,UQ) │
                          │ sent_at         │       │ plan_id (FK)    │
                          │ created_at      │       │ started_at      │
                          └─────────────────┘       │ expires_at      │
                                                    │ is_active       │
                                                    │ auto_renew      │
                                                    │ stripe_sub_id   │
                                                    │ stripe_cust_id  │
                                                    │ created_at      │
                                                    │ updated_at      │
                                                    └─────────────────┘
                                                              │
                                                              │ N:1
                                                              ▼
                                                    ┌─────────────────┐
                                                    │SubscriptionPlan │
                                                    ├─────────────────┤
                                                    │ id (PK)         │
                                                    │ name            │
                                                    │ description     │
                                                    │ price_usd       │
                                                    │ billing_cycle   │
                                                    │ max_custom_voices│
                                                    │ supported_langs │
                                                    │ daily_msg_limit │
                                                    │ priority_support│
                                                    │ family_slots    │
                                                    │ is_active       │
                                                    └─────────────────┘
                                                              ▲
                                                              │ 1:N
                                                              │
                                                    ┌─────────────────┐
                                                    │    UserVoice    │
                                                    ├─────────────────┤
                                                    │ id (PK)         │
                                                    │ user_id (FK)    │
                                                    │ voice_type      │
                                                    │ voice_id        │
                                                    │ voice_name      │
                                                    │ provider        │
                                                    │ languages       │
                                                    │ sub_plan_id(FK) │
                                                    │ expires_at      │
                                                    │ expires_w_sub   │
                                                    │ audio_sample_url│
                                                    │ is_default      │
                                                    │ is_active       │
                                                    │ deleted_at      │
                                                    │ created_at      │
                                                    │ updated_at      │
                                                    └─────────────────┘
                                                              ▲
                                                              │ 1:N
                                                              │
                                                    ┌─────────────────┐
                                                    │  SystemVoice    │
                                                    ├─────────────────┤
                                                    │ id (PK)         │
                                                    │ voice_name      │
                                                    │ provider        │
                                                    │ language        │
                                                    │ quality_score   │
                                                    │ is_active       │
                                                    └─────────────────┘
```

---

## Table Definitions

### users

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,           -- Argon2id
    name VARCHAR(120),
    phone VARCHAR(32),
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_users_username ON users(username);
CREATE INDEX ix_users_email ON users(email);
```

### refresh_tokens

```sql
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL,       -- SHA-256
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX ix_refresh_tokens_hash ON refresh_tokens(token_hash);
CREATE INDEX ix_refresh_tokens_active ON refresh_tokens(user_id, revoked_at) 
    WHERE revoked_at IS NULL;
```

### conversations

```sql
CREATE TABLE conversations (
    id CHAR(36) PRIMARY KEY,               -- UUID as string (JWT compatibility)
    user_id CHAR(36) UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) DEFAULT 'Conversation',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_conversations_user ON conversations(user_id);
```

### messages

```sql
CREATE TABLE messages (
    id CHAR(36) PRIMARY KEY,               -- UUID as string
    conversation_id CHAR(36) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    tokens_used INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_messages_conversation ON messages(conversation_id);
CREATE INDEX ix_messages_created ON messages(conversation_id, created_at DESC);
```

### memories

```sql
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_sensitive BOOLEAN DEFAULT FALSE,
    is_encrypted BOOLEAN DEFAULT FALSE,
    approved_at TIMESTAMP,                 -- NULL = pending, datetime = approved
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP                   -- Soft delete
);

CREATE INDEX ix_memories_user_approved ON memories(user_id, approved_at) 
    WHERE deleted_at IS NULL;
CREATE INDEX ix_memories_user_sensitive ON memories(user_id, is_sensitive);
CREATE INDEX ix_memories_created ON memories(user_id, created_at DESC);
```

### tasks

```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium' 
        CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    due_date DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed')),
    tags VARCHAR(500),
    auto_extracted BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE INDEX ix_tasks_user_due ON tasks(user_id, due_date) WHERE deleted_at IS NULL;
CREATE INDEX ix_tasks_user_status ON tasks(user_id, status) WHERE deleted_at IS NULL;
CREATE INDEX ix_tasks_user_created ON tasks(user_id, created_at DESC) WHERE deleted_at IS NULL;
```

### reminders

```sql
CREATE TABLE reminders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reminder_time TIMESTAMP NOT NULL,
    reminder_type VARCHAR(50) NOT NULL DEFAULT 'due_soon'
        CHECK (reminder_type IN ('due_soon', 'overdue', 'custom')),
    sent BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_reminders_pending ON reminders(user_id, reminder_time) 
    WHERE sent = FALSE;
```

### subscription_plans

```sql
CREATE TABLE subscription_plans (
    id VARCHAR(50) PRIMARY KEY,            -- 'free', 'pro', 'premium'
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price_usd DECIMAL(10,2) NOT NULL DEFAULT 0,
    billing_cycle VARCHAR(20) NOT NULL DEFAULT 'monthly'
        CHECK (billing_cycle IN ('monthly', 'yearly')),
    max_custom_voices INTEGER DEFAULT 0,
    supported_languages VARCHAR(200) DEFAULT 'en',
    daily_message_limit INTEGER DEFAULT 100,
    priority_support BOOLEAN DEFAULT FALSE,
    family_sharing_slots INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### user_subscriptions

```sql
CREATE TABLE user_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id VARCHAR(50) NOT NULL REFERENCES subscription_plans(id),
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    renewed_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    auto_renew BOOLEAN DEFAULT TRUE,
    stripe_subscription_id VARCHAR(255),
    stripe_customer_id VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE INDEX ix_user_subscriptions_active ON user_subscriptions(user_id, is_active, expires_at);
```

### user_voices

```sql
CREATE TABLE user_voices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    voice_type VARCHAR(20) NOT NULL DEFAULT 'system'
        CHECK (voice_type IN ('system', 'custom')),
    voice_id VARCHAR(255) NOT NULL,        -- Provider-specific ID
    voice_name VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    languages VARCHAR(10) DEFAULT 'en',
    subscription_plan_id VARCHAR(50) REFERENCES subscription_plans(id),
    expires_at TIMESTAMP,
    expires_with_subscription BOOLEAN DEFAULT TRUE,
    audio_sample_url VARCHAR(500),
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_user_voices_user ON user_voices(user_id) WHERE deleted_at IS NULL;
```

### system_voices

```sql
CREATE TABLE system_voices (
    id VARCHAR(50) PRIMARY KEY,            -- Provider voice ID
    voice_name VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    quality_score INTEGER DEFAULT 50,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### creator_profiles

```sql
CREATE TABLE creator_profiles (
    id CHAR(36) PRIMARY KEY,               -- Fixed: "1"
    name VARCHAR(255) NOT NULL,
    father_name VARCHAR(255),
    mother_name VARCHAR(255),
    girlfriend_name VARCHAR(255),
    family_lineage TEXT,
    birthplace VARCHAR(255),
    ancestral_roots VARCHAR(255),
    hometown VARCHAR(255),
    education_background VARCHAR(255),
    graduation_year VARCHAR(10),
    graduation_degree VARCHAR(100),
    personality TEXT,
    hobbies TEXT,
    dreams TEXT,
    github_url VARCHAR(500),
    linkedin_url VARCHAR(500),
    instagram_url VARCHAR(500),
    twitter_url VARCHAR(500),
    raghvi_name_origin TEXT,
    creation_purpose TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

## Key Design Decisions

### UUID vs String(36) IDs

| Table | ID Type | Reason |
|-------|---------|--------|
| users | UUID (native) | Primary entity, SQLAlchemy `Uuid(as_uuid=True)` |
| conversations | CHAR(36) | JWT extracts `user_id` as string; avoids bind processor issues |
| messages | CHAR(36) | Same as conversations |
| memories | UUID (native) | Independent, no JWT coupling |
| tasks | UUID (native) | Independent |
| refresh_tokens | UUID (native) | Independent |

**Note**: Conversation/Message use `String(36)` for JWT compatibility. Future sprint will unify to native UUID.

### Soft Deletes

All user-data tables use `deleted_at TIMESTAMP` for soft deletes:
- Queries filter `WHERE deleted_at IS NULL`
- Hard delete only via admin/account deletion workflow
- Enables recovery and audit trail

### Timestamps

- All `created_at`/`updated_at` use timezone-naive UTC (`datetime.now(UTC).replace(tzinfo=None)`)
- Compatible with PostgreSQL `TIMESTAMP WITHOUT TIME ZONE`
- Avoids Python 3.12+ `datetime.utcnow()` deprecation

### JSONB for Preferences

- `users.preferences`: Flexible key-value for user settings
- No schema migration needed for new preference keys

---

## Migration History

| Migration | Description |
|-----------|-------------|
| `39b25b96c42a_init.py` | Initial: users, refresh_tokens |
| `7c2d492c2a4f_add_auth_tables.py` | Auth tables (already in init) |
| `defaf42c39c7_create_conversations_and_messages_tables.py` | Chat tables |
| `b5faaa39919b_add_unique_constraint_on_conversations_.py` | UNIQUE(user_id) on conversations |
| `45baa27d1453_create_memories_table.py` | Memory system |
| `52ccf4c_feat_backend_create_task_model.py` | Task model |
| `1e0df95b33b6_create_tasks_table.py` | Tasks (duplicate?) |
| `8e2ddcc87da0_create_reminders_table.py` | Reminders |
| `12f10a85d09e_create_creator_profile_table.py` | Creator profile |
| `8af8727cf82a_create_subscription_and_voice_tables.py` | Subscriptions + voices |
| `b25e23833241_add_subscription_plans_and_user_.py` | Subscription plans + user_subscriptions |

---

## Query Patterns

### Common Access Patterns

| Query | Index Used |
|-------|------------|
| Get user by username/email | `ix_users_username`, `ix_users_email` |
| Get conversation by user | `ix_conversations_user` (UNIQUE) |
| Get recent messages | `ix_messages_created` |
| Get approved memories | `ix_memories_user_approved` |
| Get pending memories | `ix_memories_user_sensitive` + filter `approved_at IS NULL` |
| Get active tasks | `ix_tasks_user_due`, `ix_tasks_user_status` |
| Get pending reminders | `ix_reminders_pending` |
| Get active subscription | `ix_user_subscriptions_active` |
| Get user voices | `ix_user_voices_user` |

---

## Related ADRs

- [ADR-001: Memory Strategy](../03-decisions/ADR-001-memory-strategy.md)
- [ADR-004: Data Storage & Retrieval](../03-decisions/ADR-004-data-storage-and-retrieval.md)
- [ADR-005: Authentication & Authorization](../03-decisions/ADR-005-Authentication-Authorization-privacy.md)
- [ADR-012: Data Retention & Lifecycle](../03-decisions/ADR-012-data-retention-deletion-export-and-life-cycle.md)