# Developer Architecture Documentation - Agent Guide

## Purpose

This directory contains developer-focused architecture documentation for the Home Security Intelligence project. It provides implementation guides, migration patterns, and architectural decision references for developers working on the system. This is distinct from `docs/architecture/` which contains comprehensive system design documents for understanding the overall architecture.

## Quick Navigation

| Document                                               | Purpose                                    |
| ------------------------------------------------------ | ------------------------------------------ |
| [README.md](README.md)                                 | Directory overview and system diagram      |
| [model-loader-migration.md](model-loader-migration.md) | Model loader migration guide for Model Zoo |

## Directory Contents

```
developer/architecture/
  AGENTS.md                    # This file
  README.md                    # Directory overview with system diagram
  model-loader-migration.md    # Model loader migration to abstract base class
```

## Key Files

### README.md

**Purpose:** Overview of architecture documentation with navigation to system design documents.

**Contents:**

- System diagram (camera-to-dashboard pipeline)
- Technology stack table (frontend, backend, AI layers)
- Component layers (backend services, frontend hooks)
- Links to deep-dive documents in `docs/architecture/`

**When to use:** Finding the right architecture document for a specific topic.

### model-loader-migration.md

**Purpose:** Guide for migrating model loaders to use the `ModelLoaderBase` abstract base class.

**Contents:**

- Migration pattern from functional to class-based loaders
- List of 14+ loaders with migration status
- Code examples for before/after patterns
- Testing requirements and checklist
- References to source files

**Key Source Files:**

- `backend/services/model_loader_base.py` - Abstract base class
- `backend/services/clip_loader.py` - Reference implementation (CLIPLoader)
- `backend/tests/unit/services/test_model_loader_base.py` - Base class tests
- `backend/tests/unit/services/test_clip_loader.py` - Reference tests

**When to use:** Adding new model loaders or migrating existing ones to the standard interface.

## Related Resources

### System Architecture (docs/architecture/)

| Document                                                  | Description                             |
| --------------------------------------------------------- | --------------------------------------- |
| [overview.md](../../architecture/overview.md)             | High-level system design and data flow  |
| [data-model.md](../../architecture/data-model.md)         | PostgreSQL schemas and Redis structures |
| [ai-pipeline.md](../../architecture/ai-pipeline.md)       | Detection to analysis flow              |
| [real-time.md](../../architecture/real-time.md)           | WebSocket and pub/sub architecture      |
| [decisions.md](../../architecture/decisions.md)           | ADRs - why we made key choices          |
| [resilience.md](../../architecture/resilience.md)         | Error handling and graceful degradation |
| [frontend-hooks.md](../../architecture/frontend-hooks.md) | Custom React hook architecture          |

### Developer Documentation (docs/developer/)

| Document                                            | Description                                      |
| --------------------------------------------------- | ------------------------------------------------ |
| [backend-patterns.md](../backend-patterns.md)       | Repository pattern, Result type, RFC 7807 errors |
| [resilience-patterns.md](../resilience-patterns.md) | Circuit breakers, retries, prompt injection      |
| [pipeline-overview.md](../pipeline-overview.md)     | AI pipeline overview for developers              |
| [codebase-tour.md](../codebase-tour.md)             | Directory structure and key file navigation      |

### Implementation References

| Location                                | Purpose                          |
| --------------------------------------- | -------------------------------- |
| `backend/services/model_loader_base.py` | Model loader abstract base class |
| `backend/services/model_zoo.py`         | Model Zoo registry               |
| `ai/AGENTS.md`                          | AI services implementation       |
| `backend/AGENTS.md`                     | Backend implementation details   |

## Entry Points for Agents

### Adding a New Model Loader

1. Read `model-loader-migration.md` for the migration pattern
2. Implement `ModelLoaderBase[T]` interface
3. Follow the testing checklist
4. Update Model Zoo registry in `backend/services/model_zoo.py`

### Understanding System Architecture

1. Start with `README.md` for the quick overview
2. Navigate to `docs/architecture/overview.md` for full system design
3. Review specific documents based on component (AI pipeline, data model, real-time)

### Making Architecture Decisions

1. Check existing ADRs in `docs/architecture/decisions.md`
2. Review `docs/decisions/` for additional ADRs
3. Follow ADR template when adding new decisions

## Document Standards

Documents in this directory follow the developer documentation template:

```markdown
# [Topic Title]

## Overview

Brief summary of the topic.

## [Main Sections]

Implementation details, patterns, code examples.

## References

Links to related source files and documentation.
```

---

[Back to Developer Hub](../README.md) | [Back to Documentation Index](../../README.md)
