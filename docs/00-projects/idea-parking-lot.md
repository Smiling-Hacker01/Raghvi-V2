# Raghvi v2 — Idea Parking Lot

**Status:** Living Document
**Owner:** Vishal Singh Kushwaha
**Created:** 2026-07-02
**Last Updated:** 2026-07-08

## Purpose

This document captures valuable product, engineering, and research ideas that are not part of the current milestone.

An idea belongs here when it is promising but does not directly support the current MVP or active Architecture Decision Record. Recording it protects the project from feature creep while ensuring useful ideas are not lost.

## How to Use This Document

For each new idea:

1. Add it to the appropriate section.
2. Mark its horizon: **MVP**, **Roadmap**, or **North Star**.
3. State the user value and why it is not being built now.
4. Link it to a future ADR, issue, or sprint when it becomes active.

No item should move into implementation without a product decision, technical design, and a defined success criterion.

## Decision Horizons

| Horizon    | Meaning                                                |
| ---------- | ------------------------------------------------------ |
| MVP        | Required to validate Raghvi’s core daily-use loop.     |
| Roadmap    | Valuable after the MVP has proven the core experience. |
| North Star | Long-term vision; no implementation commitment yet.    |

## Active MVP Focus

The current MVP focus is:

* Natural conversation
* User-controlled long-term memory
* Context-aware guidance
* Project continuity
* Basic proactive briefings and reminders, only with user permission
* A small set of safe, explicit user-approved actions

Anything outside this focus should be parked unless a new decision explicitly changes MVP scope.

## Parked Product Ideas

| Idea                          | Horizon       | User Value                                                      | Why Not Now                                                                           | Revisit When                                                       |
| ----------------------------- | ------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Voice-first conversations     | Roadmap       | Makes Raghvi feel more natural and accessible.                  | Voice introduces speech recognition, audio permissions, streaming, and UX complexity. | After the chat and memory loop is stable.                          |
| WhatsApp message assistance   | Roadmap       | Helps users communicate faster.                                 | Platform restrictions, privacy concerns, and high risk of unwanted actions.           | After the permission and action-confirmation model is mature.      |
| Email drafting and sending    | Roadmap       | Reduces repetitive professional work.                           | Requires account integrations, OAuth, permissions, and auditability.                  | After authentication and tool execution are proven.                |
| Browser automation            | Roadmap       | Can complete repetitive web workflows.                          | Fragile integrations and high security risk.                                          | After a robust tool-permission framework exists.                   |
| Calendar integration          | Roadmap       | Enables useful meeting and schedule awareness.                  | Requires external OAuth integration and a reliable notification model.                | After proactive intelligence foundations are complete.             |
| Memory dashboard              | MVP / Roadmap | Gives users visibility, editing, deletion, and trust in memory. | The MVP needs basic memory controls first; a full visual dashboard can follow.        | Build a minimal version alongside the memory domain; expand later. |
| Relationship memory           | Roadmap       | Helps Raghvi remember important people and occasions.           | Sensitive personal data needs careful consent, visibility, and deletion controls.     | After the privacy model and memory controls are validated.         |
| Habit learning                | Roadmap       | Enables more useful proactive suggestions.                      | Requires sufficient usage data and safeguards against intrusive behavior.             | After users can configure proactive preferences.                   |
| Emotional support mode        | North Star    | Makes conversations more empathetic and supportive.             | Requires careful safety design, boundaries, and evaluation.                           | After core companion behavior is reliable.                         |
| Family mode                   | North Star    | Supports shared household coordination.                         | Requires multi-user identity, permissions, and privacy boundaries.                    | After single-user memory and account design are mature.            |
| Multi-device sync             | Roadmap       | Lets users continue across phone, desktop, and web.             | Adds conflict resolution, device security, and sync complexity.                       | After the backend API and Android MVP are stable.                  |
| Desktop and web clients       | Roadmap       | Expands access beyond Android.                                  | The project needs one excellent client before multiple clients.                       | After Android-first workflows are validated.                       |
| Wearable support              | North Star    | Enables lightweight reminders and quick interactions.           | Requires platform-specific design and notification constraints.                       | After mobile proactive intelligence is successful.                 |
| Smart-home integrations       | North Star    | Lets Raghvi assist with physical-world routines.                | Requires many integrations and stronger authorization boundaries.                     | After tool execution and permission controls mature.               |
| Knowledge graph visualization | Roadmap       | Helps users explore projects, concepts, and relationships.      | The memory model should be validated before visualizing its relationships.            | After semantic and project memory are stable.                      |
| PDF and document chat         | Roadmap       | Lets users learn from personal documents.                       | Requires ingestion, storage, retrieval, permissions, and evaluation.                  | After core memory retrieval works reliably.                        |
| Image understanding and OCR   | Roadmap       | Helps users capture information from screenshots and images.    | Adds multimodal processing, storage, and privacy complexity.                          | After text-first workflows are stable.                             |
| Image generation              | North Star    | Supports creative tasks.                                        | Does not strengthen the core memory-and-continuity loop.                              | Only if user research shows strong demand.                         |
| Multi-agent workflows         | North Star    | Could support specialized planning and execution.               | Adds orchestration complexity before the single-agent loop is proven.                 | After ADR-002 and a stable single-agent architecture.              |
| Plugin ecosystem              | North Star    | Lets third parties extend Raghvi.                               | Requires stable APIs, sandboxing, and security review.                                | After internal tool APIs are mature.                               |
| Hands-free voice coding agent | North Star    | Lets users build applications entirely through conversational voice commands while away from keyboard. Raghvi gathers requirements, creates repos, writes code, tests, and asks clarifying questions midway. | Requires advanced voice streaming, robust agentic autonomous coding, complex state management, and reliable testing loops without manual intervention. | After voice conversations, text-based coding assistance, and multi-agent workflows are mature. |

## Parked Engineering Ideas

| Idea                      | Horizon    | Value                                                        | Why Not Now                                                       | Revisit When                                                            |
| ------------------------- | ---------- | ------------------------------------------------------------ | ----------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Microservices             | Roadmap    | Independent scaling and deployment for proven bottlenecks.   | A single-developer project benefits more from a modular monolith. | When a module has measurable scaling or ownership needs.                |
| Kubernetes                | North Star | Advanced orchestration for distributed production workloads. | Adds substantial operational complexity.                          | When multiple independently deployed services require it.               |
| Dedicated vector database | Roadmap    | May improve retrieval scale and operational isolation.       | PostgreSQL with pgvector is likely sufficient for the MVP.        | When retrieval scale or latency measurements justify it.                |
| Knowledge graph database  | Roadmap    | May improve relationship-heavy memory queries.               | Adds another datastore before graph needs are proven.             | When project and relationship queries exceed relational modeling needs. |
| Event bus                 | Roadmap    | Supports decoupled asynchronous workflows.                   | A simple background-job approach is easier initially.             | When multiple modules need durable event-driven workflows.              |
| Multi-region deployment   | North Star | Improves global resilience and latency.                      | Not justified before product validation and real traffic.         | When users and reliability requirements demand it.                      |
| Offline-first mode        | Roadmap    | Improves usability during poor connectivity.                 | Requires local storage, synchronization, and conflict resolution. | After online-first workflows are stable.   
| Knowledge Graph and GraphRAG Evaluation          | Roadmap | Enables Raghvi to answer relationship-heavy questions by combining semantic retrieval with explicit connections between users, projects, tasks, decisions, people, events, and goals. It can improve multi-hop reasoning, project continuity, dependency analysis, and connected planning. | GraphRAG depends on clean entities, reliable relationships, high-quality memory capture, and measurable retrieval gaps. Introducing a dedicated graph database or graph-first retrieval before those foundations exist would add unnecessary operational complexity and could amplify incorrect or incomplete memory relationships. | Evaluate after PostgreSQL + pgvector memory retrieval is stable and the project has evidence of relationship-heavy retrieval failures. Trigger evaluation when users frequently ask multi-hop questions, semantic retrieval misses connected context, `memory_links` becomes difficult to query or maintain, or graph traversal demonstrably improves answer quality in a benchmark. |
| LangGraph Evaluation for Durable Agent Workflows | Roadmap | Supports stateful, multi-step AI workflows with branching, retries, tool execution, approval checkpoints, pause-and-resume behavior, and durable workflow state. This is valuable for complex planning and user-approved task execution.                                                   | The MVP orchestration flow is intentionally simple: retrieve context, reason, optionally invoke one approved tool, respond, and evaluate memory. Adding a workflow framework before Raghvi has proven multi-step workflows would increase abstraction, dependency, debugging, and operational complexity.                           | Evaluate when Raghvi needs multiple tool calls in one task, approval pauses, retry handling, background execution, long-running plans, or durable task state that becomes difficult to manage with the custom orchestration layer.                                                                                                                                                   |

## Future Architecture Path: Graph-Aware Intelligence

Raghvi’s long-term architecture may evolve from semantic retrieval toward graph-aware intelligence. This is a roadmap direction, not an MVP commitment.

### Phase 1 — Structured Memory and Hybrid Retrieval

The MVP uses PostgreSQL, pgvector, structured memory metadata, and `memory_links`.

```text
User request
  ↓
Intent and project filters
  ↓
Structured memory query
  ↓
Semantic similarity retrieval
  ↓
Ranked context
  ↓
LLM response
```

This phase validates memory quality, user controls, retrieval relevance, and relationship capture without introducing a dedicated graph database.

### Phase 2 — Selective Graph Traversal

After `memory_links` contains reliable relationships, Raghvi may add graph traversal for selected queries.

Examples:

* Which unfinished tasks are blocking my portfolio release?
* What decisions led to the current architecture?
* Which goals, tasks, and deadlines are connected to this project?
* What commitments are related to a specific person or event?

At this stage, relationships may still be stored and queried through PostgreSQL.

### Phase 3 — GraphRAG Evaluation

GraphRAG will be evaluated when relationship-aware retrieval can be shown to improve results over standard hybrid retrieval.

A GraphRAG workflow may look like:

```text
User request
  ↓
Identify relevant entities and intent
  ↓
Semantic retrieval of relevant memories
  ↓
Traverse related projects, tasks, decisions, and events
  ↓
Build a connected evidence set
  ↓
Generate an answer with relationship-aware context
```

GraphRAG must not be adopted solely because it is technically advanced. Adoption requires evidence that it improves retrieval quality, reduces missing context, or enables user-important multi-hop questions that the existing architecture cannot answer reliably.

### Phase 4 — Dedicated Knowledge Graph, If Justified

A dedicated graph database may be introduced only when PostgreSQL-based relationship modeling becomes a measurable constraint.

Potential adoption signals include:

* Relationship-heavy queries are common and slow.
* Multi-hop traversal is difficult to express or maintain in relational queries.
* Entity and relationship volume grows substantially.
* Graph-aware retrieval produces consistently better evaluation results.
* The operational cost is justified by demonstrated product value.

Until then, PostgreSQL remains the source of truth for structured memory and relationships.

## Open Questions to Revisit

* What level of proactivity do users find helpful rather than distracting?
* Which memory categories should require explicit confirmation before saving?
* How should Raghvi resolve conflicting or outdated memories?
* What retention periods should apply to episodic memories?
* Which Android actions are safe enough for the MVP?
* What measurable signals should trigger extraction of a module into a separate service?
* How will we evaluate whether Raghvi’s memory is accurate and useful?

## Promotion Rules

An idea may move out of this document only when all of the following are true:

* It has a clear user problem.
* It has a defined success metric.
* It fits the current roadmap horizon.
* Its privacy and security implications are understood.
* It has an owner, technical design, and estimated scope.
* It does not compromise the active milestone.

## Change Log

| Date       | Change                    |
| ---------- | ------------------------- |
| 2026-07-02 | Initial document created. |
