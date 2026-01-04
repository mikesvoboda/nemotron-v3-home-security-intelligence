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
  AGENTS.md              # This file
  alerts.md              # Alert system for developers
  batching-logic.md      # Batch aggregation details
  codebase-tour.md       # Directory structure and key file navigation
  data-model.md          # Database schema for developers
  detection-service.md   # Detection service details
  hooks.md               # Pre-commit hook configuration
  local-setup.md         # Quick development environment setup
  pipeline-overview.md   # AI pipeline for developers
  risk-analysis.md       # Risk analysis service details
  video.md               # Video processing details
```

## Key Files

| File                   | Purpose                                           |
| ---------------------- | ------------------------------------------------- |
| `local-setup.md`       | Quick development environment setup               |
| `codebase-tour.md`     | Directory structure and key file navigation       |
| `hooks.md`             | Pre-commit hook configuration and troubleshooting |
| `alerts.md`            | Alert system implementation for developers        |
| `batching-logic.md`    | Batch aggregation timing and logic                |
| `data-model.md`        | Database schema documentation                     |
| `detection-service.md` | Detection service implementation                  |
| `pipeline-overview.md` | AI pipeline overview for developers               |
| `risk-analysis.md`     | Risk analysis service implementation              |
| `video.md`             | Video processing implementation                   |

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
