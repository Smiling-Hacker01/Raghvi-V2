# Documentation Index

This directory contains all project documentation organized by category.

---

## Quick Start

| Document | Description |
|----------|-------------|
| [Root README](../README.md) | Project overview, setup, API reference, commands |
| [MVP Delivery Plan](04-implementations/mvp-delivery-plan.md) | Milestone roadmap (M0–M8) |
| [Product Brief](00-projects/product-brief.md) | Vision, MVP scope, success metrics |

---

## Product & Vision

| Document | Description |
|----------|-------------|
| [North Star](00-projects/north-star.md) | Vision, mission, product identity, pillars |
| [Product Brief](00-projects/product-brief.md) | Executive summary, problem, MVP, risks |
| [Product Constitution](00-projects/product-constitution.md) | Product principles (when available) |
| [Identity Manifesto](00-projects/raghvi-identity-manifesto.md) | Brand identity |
| [Glossary](00-projects/glossary.md) | Terminology definitions |
| [User Research](01-products/user-research.md) | User research findings |
| [MVP Definition](01-products/mvp-definition.md) | Detailed MVP requirements |

---

## Architecture

| Document | Description |
|----------|-------------|
| [Architecture Principles](02-architecture/architecture-principles.md) | Core architectural principles |
| [AI Architecture](architecture/ai-architecture.md) | Multi-provider AI chain, failover, adapter pattern |
| [Memory Architecture](architecture/memory-architecture.md) | Memory layers, lifecycle, retrieval, encryption |
| [Voice Architecture](architecture/voice-architecture.md) | Voice provider chain, synthesis, cloning |
| [Data Model](architecture/data-model.md) | ER diagram, table descriptions |

---

## API Reference

| Document | Description |
|----------|-------------|
| [API Reference](api/API.md) | Complete REST API reference with all endpoints |

---

## Architecture Decision Records (ADRs)

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](03-decisions/ADR-001-memory-strategy.md) | Memory Strategy | Proposed |
| [ADR-002](03-decisions/ADR-002-ai-orchestration.md) | AI Orchestration | Accepted |
| [ADR-003](03-decisions/ADR-003-backend-framework-and-runtime.md) | Backend Framework & Runtime | Accepted |
| [ADR-004](03-decisions/ADR-004-data-storage-and-retrieval.md) | Data Storage & Retrieval | Accepted |
| [ADR-005](03-decisions/ADR-005-Authentication-Authorization-privacy.md) | Authentication & Authorization | Accepted |
| [ADR-006](03-decisions/ADR-006-proactive-intelligence-and-background-jobs.md) | Proactive Intelligence | Accepted |
| [ADR-007](03-decisions/ADR-007-android-device-integration-action.md) | Android Device Integration | Accepted |
| [ADR-008](03-decisions/ADR-008-api-contracts-and-client-communication.md) | API Contracts | Accepted |
| [ADR-009](03-decisions/ADR-009-quality-engineering-and-ci-integration.md) | Quality Engineering & CI | Accepted |
| [ADR-010](03-decisions/ADR-010-observability-logging-monitoring-and-incident-report.md) | Observability | Accepted |
| [ADR-011](03-decisions/ADR-011-deployment-environments-secrets-and-release-strategy.md) | Deployment & Secrets | Accepted |
| [ADR-012](03-decisions/ADR-012-data-retention-deletion-export-and-life-cycle.md) | Data Retention & Lifecycle | Accepted |
| [ADR-013](03-decisions/ADR-013-ai-model-provider-strategy-cost-controls-and-fallbacks.md) | AI Provider Strategy | Accepted |
| [ADR-014](03-decisions/ADR-014-security-threat-model-and-abuse-prevention.md) | Security Threat Model | Accepted |

---

## Sprint Documentation

| Sprint | Milestone | Document |
|--------|-----------|----------|
| Sprint 00 | M0 Foundation | [sprint-00-foundation.md](05-sprints/sprint-00-foundation.md) |
| Sprint 01 | M1 Auth | [sprint-01-auth.md](05-sprints/sprint-o1-auth.md) |
| Sprint 02 | M2 Chat | [sprint-02-chat.md](05-sprints/sprint-02-chat.md) |
| Sprint 03 | M2 Memory | [sprint-03-memory.md](05-sprints/sprint-03-memory.md) |
| Sprint 04 | M2 Tasks | [sprint-04-tasks.md](05-sprints/sprint-04-tasks.md) |
| Sprint 05 | M3+ Voice & Payments | *(not yet documented)* |

---

## Implementation Plans

| Document | Description |
|----------|-------------|
| [MVP Delivery Plan](04-implementations/mvp-delivery-plan.md) | Full milestone roadmap M0–M8 |
| [M2 Plan](04-implementations/m2-plan.md) | M2 implementation details |

---

## Deployment & Operations

| Document | Description |
|----------|-------------|
| [Deployment Guide](deployment/DEPLOYMENT.md) | Production deployment (when created) |
| [Operations Guide](operations/OPERATIONS.md) | Monitoring, backup, incidents (when created) |

---

## Project Ideas & Parking Lot

| Document | Description |
|----------|-------------|
| [Idea Parking Lot](00-projects/idea-parking-lot.md) | Future feature ideas |
| [M2 Plan](04-implementations/m2-plan.md) | M2 detailed plan |

---

## Navigation Tips

- **New developers**: Start with [Root README](../README.md) → [Product Brief](00-projects/product-brief.md) → [MVP Delivery Plan](04-implementations/mvp-delivery-plan.md)
- **Architecture questions**: Check [Architecture Principles](02-architecture/architecture-principles.md) and relevant ADRs in [03-decisions/](03-decisions/)
- **API integration**: Use [API Reference](api/API.md)
- **Sprint history**: Browse [05-sprints/](05-sprints/) for detailed sprint plans and acceptance criteria
- **Future work**: Check [Idea Parking Lot](00-projects/idea-parking-lot.md) and [MVP Delivery Plan](04-implementations/mvp-delivery-plan.md#7-milestone-overview)