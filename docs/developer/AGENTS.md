# Developer Documentation - Agent Guide

## Purpose

This directory contains developer-focused documentation for the Home Security Intelligence project. It is part of the hub-and-spoke documentation architecture, with [developer-hub.md](../developer-hub.md) as the central hub.

## Target Audience

- Software developers contributing to the project
- Engineers extending the system with new features
- Technical team members debugging or reviewing code

## Directory Contents

```
developer/
  AGENTS.md               # This file
  README.md               # Developer documentation hub and index
  accessibility.md        # WCAG compliance, ARIA patterns, a11y testing
  alerts.md               # Alert system for developers
  backend-patterns.md     # Repository pattern, Result type, RFC 7807 errors
  batching-logic.md       # Batch aggregation details
  clip-generation.md      # Event video clips, FFmpeg integration, API endpoints
  codebase-tour.md        # Directory structure and key file navigation
  data-model.md           # Database schema for developers
  detection-service.md    # Detection service details
  entity-tracking.md      # Re-identification, CLIP embeddings, cross-camera matching
  keyboard-patterns.md    # Keyboard shortcuts and command palette
  local-setup.md          # Quick development environment setup
  pipeline-overview.md    # AI pipeline for developers
  prompt-management.md    # Prompt template management and versioning
  pwa-implementation.md   # PWA features, push notifications, offline caching
  redis-key-conventions.md # Redis key naming patterns and best practices
  resilience-patterns.md  # Circuit breakers, retries, prompt injection prevention
  risk-analysis.md        # Risk analysis service details
  ux-patterns.md          # Toast notifications, page transitions, skeleton loaders
  video.md                # Video processing details
  visualization-components.md # Dashboard visualization component patterns
```

## Key Files

| File                          | Purpose                                           |
| ----------------------------- | ------------------------------------------------- |
| `local-setup.md`              | Quick development environment setup               |
| `codebase-tour.md`            | Directory structure and key file navigation       |
| `keyboard-patterns.md`        | Keyboard shortcuts and command palette patterns   |
| `accessibility.md`            | WCAG compliance, ARIA patterns, a11y testing      |
| `backend-patterns.md`         | Repository pattern, Result types, RFC 7807 errors |
| `pwa-implementation.md`       | PWA manifest, push notifications, offline caching |
| `ux-patterns.md`              | Toast notifications, page transitions, skeletons  |
| `resilience-patterns.md`      | Circuit breakers, retry logic, prompt injection   |
| `alerts.md`                   | Alert system implementation for developers        |
| `batching-logic.md`           | Batch aggregation timing and logic                |
| `clip-generation.md`          | Event video clips, FFmpeg integration, API        |
| `data-model.md`               | Database schema documentation                     |
| `detection-service.md`        | Detection service implementation                  |
| `entity-tracking.md`          | Re-ID service, CLIP embeddings, entity APIs       |
| `pipeline-overview.md`        | AI pipeline overview for developers               |
| `risk-analysis.md`            | Risk analysis service implementation              |
| `video.md`                    | Video processing implementation                   |
| `redis-key-conventions.md`    | Redis key naming patterns and best practices      |
| `prompt-management.md`        | Prompt template management and versioning         |
| `visualization-components.md` | Dashboard visualization component patterns        |
| `README.md`                   | Developer documentation hub and index             |

## Related Documentation

Most developer documentation already exists in other locations:

| Topic          | Existing Location                     | Notes                           |
| -------------- | ------------------------------------- | ------------------------------- |
| Testing        | `docs/development/testing.md`         | Comprehensive test guide        |
| Contributing   | `docs/development/contributing.md`    | PR workflow, commit conventions |
| Code Patterns  | `docs/development/patterns.md`        | Async patterns, error handling  |
| Architecture   | `docs/architecture/overview.md`       | System design                   |
| Data Model     | `docs/architecture/data-model.md`     | Database schemas                |
| AI Pipeline    | `docs/architecture/ai-pipeline.md`    | Detection flow                  |
| Real-time      | `docs/architecture/real-time.md`      | WebSocket architecture          |
| Frontend Hooks | `docs/architecture/frontend-hooks.md` | React custom hooks              |
| Decisions      | `docs/architecture/decisions.md`      | ADRs                            |

## Navigation

Start at [Developer Hub](../developer-hub.md) for the complete developer documentation index.

## Document Standards

All spoke documents in this directory should follow the template:

```markdown
# [Topic Title]

> One-sentence summary.

**Time to read:** ~X min
**Prerequisites:** [Link] or "None"

---

[Content]

---

## Next Steps

- [Related Doc](../developer-hub.md)

---

[Back to Developer Hub](../developer-hub.md)
```
