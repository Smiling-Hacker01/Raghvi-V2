# Raghvi v2 — Glossary

**Status:** Living Document
**Owner:** Vishal Singh Kushwaha
**Created:** 2026-07-02
**Last Updated:** 2026-07-02

## Purpose

This glossary defines the shared vocabulary used across Raghvi v2 product, architecture, decision, and sprint documents.

When a term in this glossary conflicts with an informal use elsewhere, this glossary is the source of truth. New terms should be added here when they become important to product behavior, architecture, security, or engineering decisions.

## Core Product Terms

### Raghvi

Raghvi is an Android-first AI companion designed to help users with everyday work, planning, learning, communication, and personal organization. Raghvi aims to provide continuity through user-controlled memory, context-aware guidance, and permission-based proactive assistance.

### Companion

A product behavior model in which Raghvi is helpful, respectful, and context-aware over time. A companion can make useful suggestions and provide continuity, but does not take external actions without the permissions and confirmations required by the user’s settings.

### Proactive Assistance

Helpful information, reminders, briefings, or suggestions initiated by Raghvi rather than requested in the current conversation. Proactive assistance must be based on relevant context, user preferences, configured permissions, and interruption rules such as quiet hours.

### Proactive Intelligence

The domain responsible for deciding whether Raghvi should remain silent, surface a suggestion, generate a reminder, create a briefing, or request confirmation for a possible action. It uses time, tasks, calendar data, user preferences, memory, and permission settings as inputs.

### Daily Briefing

A user-enabled summary of relevant information for a time period, such as today’s tasks, calendar events, priorities, reminders, or project progress.

### User Sovereignty

The principle that users remain in control of their data, memory, notifications, permissions, and external actions. Users must be able to view, edit, delete, export, and disable applicable data and capabilities.

### Permission Model

The rules that define what Raghvi may access, suggest, or do. Permissions are granular, revocable, visible to the user, and scoped to specific capabilities such as notifications, calendar access, contacts, or device actions.

### Confirmation

An explicit user approval required before Raghvi performs an external or potentially consequential action, such as sending a message, placing a call, deleting data, or modifying a calendar event.

## AI and Conversation Terms

### Large Language Model (LLM)

A machine-learning model that understands and generates natural language. In Raghvi, an LLM is one component of the system and is used for language understanding, reasoning support, response generation, classification, and planning assistance.

### Conversation

A sequence of messages between a user and Raghvi within a session or across related sessions.

### Conversation History

The stored record of messages exchanged during a conversation. Conversation history provides traceability and short-term context but is not equivalent to long-term memory.

### Session

A bounded period of interaction, usually beginning when a user starts or resumes a conversation and ending after inactivity, explicit closure, or a system-defined timeout.

### Context

The information selected for the current AI interaction. Context may include recent messages, relevant memories, active tasks, project state, permissions, time, and device or calendar information when the user has allowed access.

### Context Engine

The component that gathers, filters, ranks, and assembles relevant information for a specific user request or proactive interaction.

### Reasoning Engine

The component responsible for interpreting a user’s intent, selecting relevant context, deciding whether a tool or plan is needed, and producing structured instructions for the response generator or tool executor.

### Response Generator

The component that turns structured reasoning, retrieved context, and tool results into a natural-language response in the user’s preferred tone and language.

### Planner

The component that converts a goal or complex request into a sequence of smaller steps. A planner may ask for clarification, propose a plan, invoke tools, and track progress.

### Agent

A bounded software component that can reason about a task, use approved tools, and return a result. Raghvi will begin with a controlled single-agent workflow; specialized multi-agent workflows are a future possibility, not an MVP requirement.

### Tool

A controlled capability that Raghvi can invoke to retrieve information or perform an approved operation. Examples include checking a calendar, creating a reminder, opening an Android application, or drafting a message.

### Tool Execution

The process of validating permissions, preparing tool inputs, invoking a tool, handling its result, and recording an audit event.

## Memory Terms

### Memory

A durable, user-related piece of information that Raghvi may use in future interactions. Memory is distinct from raw chat history and must be stored, retrieved, updated, and deleted according to user controls and safety rules.

### Working Memory

Temporary context used while handling the current conversation or task. Working memory is not intended to persist indefinitely.

### Episodic Memory

A summarized record of a meaningful interaction, event, milestone, or experience. Example: “On July 2, 2026, Vishal completed the memory strategy decision for Raghvi v2.”

### Semantic Memory

A stable fact, preference, goal, or piece of user knowledge that can remain useful across conversations. Example: “Vishal prefers structured, production-oriented engineering guidance.”

### Project Memory

Memory related to an ongoing project, including goals, decisions, milestones, current status, tasks, architecture choices, and unresolved questions.

### Preference Memory

Memory about how a user prefers Raghvi to communicate, plan, format information, use language, or assist with tasks.

### Procedural Memory

Memory about how a user prefers a repeated task to be completed. Example: a preferred format for a daily plan or a preferred workflow for code reviews. Procedural memory is planned for a later phase.

### Relationship Memory

User-approved memory about important people, relationships, and occasions. This category is sensitive and requires clear consent and visibility controls.

### Habit Memory

A pattern inferred from repeated user behavior, such as regularly planning work in the morning. Habit memory must be used carefully and only for user-approved proactive assistance.

### Memory Manager

The service responsible for deciding whether information should become memory, classifying its type, assigning confidence and importance, detecting duplicates or conflicts, applying retention rules, and persisting or updating the memory.

### Memory Capture

The process of identifying potentially useful information from a conversation, tool result, or user-provided data.

### Memory Retrieval

The process of finding and ranking memories relevant to a user request, active task, or proactive opportunity.

### Memory Confidence

A score representing how reliable a memory is. Confidence depends on factors such as whether the user explicitly stated the information, whether it was inferred, how recently it was confirmed, and whether conflicting information exists.

### Memory Importance

A score representing the likely long-term value of a memory. Important memories are more likely to be retained, retrieved, and protected from automatic pruning.

### Memory Provenance

Metadata describing where a memory came from, such as an explicit user statement, a calendar integration, a tool result, or an inference. Provenance helps users understand why a memory exists.

### Memory Lifecycle

The sequence through which a memory moves: capture, evaluation, classification, storage, retrieval, update, archival, and deletion or forgetting.

### Memory Conflict

A situation in which two memories cannot both be current or correct. Example: “The user prefers Java” and “The user now prefers Kotlin for Android development.”

### Memory Pruning

The controlled reduction, archival, or deletion of low-value, outdated, duplicate, or expired memories according to retention rules and user controls.

### Memory Dashboard

A user-facing interface for viewing, editing, deleting, pinning, merging, exporting, and managing saved memories.

### Knowledge Relationship

A structured connection between memories, projects, people, concepts, or tasks. Example: a project memory may be related to a technology preference and an architecture decision.

### Knowledge Graph

A representation of entities and their relationships. Raghvi may use graph-like relationships within its memory model without requiring a dedicated graph database in the MVP.

## Architecture and Data Terms

### Modular Monolith

A single deployable application organized into strongly separated modules with clear boundaries, interfaces, ownership, and tests. Raghvi will use a modular monolith initially to preserve development speed and maintainability while keeping future extraction paths open.

### Module

A cohesive unit of code organized around a business capability, such as authentication, memory, conversation, planning, notifications, or tool execution.

### Domain

A business area with its own concepts, rules, data, and behavior. For example, Memory and Proactive Intelligence are separate domains.

### API

An application programming interface through which the Android client, backend modules, or external integrations communicate.

### REST API

An HTTP-based API style commonly used for client-server communication through resources, methods, and structured request and response bodies.

### WebSocket

A persistent connection that enables real-time, bidirectional communication between the Android app and backend.

### Background Job

Work performed outside the main request-response path, such as generating embeddings, processing memory candidates, sending scheduled notifications, or running proactive checks.

### Worker

A process that executes background jobs.

### Event

A recorded occurrence that may trigger downstream processing. Example: “memory_created,” “task_due,” or “calendar_event_upcoming.”

### Audit Log

A tamper-aware record of important system actions, especially permission checks, memory changes, tool invocations, confirmations, and external actions.

### PostgreSQL

The primary relational database planned for Raghvi’s backend. It will store structured application data such as users, conversations, memories, tasks, permissions, and audit records.

### pgvector

A PostgreSQL extension that stores and searches vector embeddings. It enables similarity search for memory retrieval while keeping early-stage data architecture simple.

### Embedding

A numerical representation of text or other content used to compare semantic similarity. Embeddings help retrieve relevant memories even when the wording differs.

### Redis

An in-memory data store that may be used for caching, short-lived state, rate limiting, queues, or coordination. Its exact role will be defined in a future ADR.

### Object Storage

A storage service for files such as attachments, exports, generated reports, and user-approved documents.

## Security and Privacy Terms

### Sensitive Data

Information that could cause harm if exposed or misused, including passwords, OTPs, financial details, government identifiers, private credentials, and other protected personal information.

### Secret

A credential or value that grants access to a system, account, service, or device. Secrets must never be stored as ordinary Raghvi memory.

### Data Minimization

The principle of collecting and retaining only the information needed to provide a requested or enabled capability.

### Least Privilege

The principle that Raghvi receives only the minimum permissions necessary for a specific feature or action.

### Consent

A clear, informed user choice to enable a feature, share data, or grant a permission. Consent must be revocable.

### Quiet Hours

User-configured periods during which Raghvi should avoid non-urgent notifications or proactive interactions.

### External Action

An operation that affects a system outside Raghvi’s internal state, such as sending a message, making a call, creating a calendar event, opening an application, or changing device settings.

## Product Planning Terms

### MVP

Minimum Viable Product. The smallest version of Raghvi that can validate its core value: useful conversation with continuity through user-controlled memory and safe, permission-based proactive help.

### Roadmap

A prioritized plan for capabilities expected after the MVP, subject to validation, technical feasibility, and user feedback.

### North Star

The long-term product vision that guides decisions without becoming an immediate implementation commitment.

### Architecture Decision Record (ADR)

A document that records a significant technical decision, its context, options considered, rationale, consequences, risks, and future reconsideration criteria.

### Decision Gate

A checkpoint at which a technical or product decision is reviewed and explicitly accepted before dependent work begins.

### Idea Parking Lot

A living document for valuable ideas that are not part of the active milestone. It protects focus while ensuring ideas are not lost.

### Sprint

A time-boxed period of planned work with a defined goal, scope, and review outcome.

## Document Maintenance Rules

* Add a term when it appears repeatedly across documents or has architectural, security, or product significance.
* Keep definitions concise, specific, and implementation-neutral unless a technology choice has already been accepted.
* Update definitions when an ADR changes the meaning or scope of a term.
* Link future documents to this glossary rather than redefining shared concepts inconsistently.
