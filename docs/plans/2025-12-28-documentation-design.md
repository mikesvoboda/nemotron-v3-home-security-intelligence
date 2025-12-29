# Documentation Structure Design

> Design for human-readable documentation covering all audiences.

**Date:** 2025-12-28
**Status:** Approved

## Overview

Create comprehensive documentation for the Home Security Intelligence project targeting multiple audiences:

- Non-technical users (family members using the dashboard)
- Future maintainer (yourself in 6 months)
- Technical contributors (friends, open source community)

## Current State

- Root README.md is excellent - developer-focused, comprehensive
- docs/ has 20+ files but no navigation/index
- 150 AGENTS.md files for AI code navigation (keep as-is)
- Missing: user guides, architecture deep-dives, consolidated navigation

## Proposed Structure

```
README.md                    # Keep as-is, add link to docs/
docs/
  README.md                  # NEW - Index/navigation for all docs

  # User-facing (non-technical) - NEW
  user-guide/
    getting-started.md       # First steps after installation
    using-the-dashboard.md   # Feature walkthrough with screenshots
    understanding-alerts.md  # Risk levels, when to worry

  # Architecture (future-you) - NEW
  architecture/
    overview.md              # High-level system design
    ai-pipeline.md           # Detection → batching → analysis
    data-model.md            # Database schema and relationships
    decisions.md             # ADR-style "why we chose X"

  # Existing docs (reorganize references)
  AI_SETUP.md                # Keep
  DOCKER_DEPLOYMENT.md       # Keep
  RUNTIME_CONFIG.md          # Keep
  ROADMAP.md                 # Keep
  plans/                     # Keep
  decisions/                 # Keep
```

## docs/README.md Content

Navigation hub that routes readers by audience:

```markdown
# Documentation

> Detailed guides for the Home Security Intelligence system.
> For quick start and overview, see the [main README](../README.md).

## By Audience

### Users

- [Getting Started](user-guide/getting-started.md)
- [Using the Dashboard](user-guide/using-the-dashboard.md)
- [Understanding Alerts](user-guide/understanding-alerts.md)

### Architecture

- [System Overview](architecture/overview.md)
- [AI Pipeline](architecture/ai-pipeline.md)
- [Data Model](architecture/data-model.md)
- [Design Decisions](architecture/decisions.md)

### Development

- [AI Setup](AI_SETUP.md)
- [Docker Deployment](DOCKER_DEPLOYMENT.md)
- [Runtime Configuration](RUNTIME_CONFIG.md)
- [Roadmap](ROADMAP.md)

### Reference

- [Plans & Designs](plans/)
- [Architectural Decisions](decisions/)
```

## User Guide Details

### getting-started.md

- What the system does (plain English)
- How to access the dashboard
- What you'll see on first load
- Mock data vs. real data explanation

### using-the-dashboard.md

- Risk Gauge - 0-100 score, color coding
- Camera Grid - active cameras, click to view
- Event Feed - live activity stream
- Event Timeline - filtering options
- Event Details - summary, reasoning, detections
- Include screenshots of mock data

### understanding-alerts.md

- Risk levels: Low (0-30), Medium (31-60), High (61-80), Critical (81-100)
- Example scenarios at each level
- What "reasoning" tells you
- When to check vs. ignore
- False positives explanation

## Architecture Details

### overview.md

- Expanded system diagram (mermaid)
- Component responsibilities
- Technology choices table with rationale
- Communication patterns (REST, WebSocket, Redis)
- Deployment topology (Docker vs. native)

### ai-pipeline.md

- File watcher flow
- RT-DETRv2 integration details
- Batching logic (90s windows, idle timeout, fast-path)
- Nemotron prompt structure and output
- Risk score calculation

### data-model.md

- Entity relationship diagram
- Table explanations (cameras, detections, events, gpu_stats)
- Key relationships
- Ephemeral vs. permanent storage
- Retention and cleanup

### decisions.md (ADR-style)

- SQLite over Postgres - single-user simplicity
- Redis for queues + pub/sub
- Batch detections for LLM context
- Hybrid deployment for GPU access
- No auth for trusted network

## Implementation Notes

- User guide should be screenshot-heavy, jargon-free
- Architecture docs explain "why" not just "what"
- Link existing docs rather than duplicating
- Keep root README unchanged except adding docs/ link
- **Use Opus model for all document creation** for deep, thoughtful content

## Files to Create

1. `docs/README.md` - navigation index
2. `docs/user-guide/getting-started.md`
3. `docs/user-guide/using-the-dashboard.md`
4. `docs/user-guide/understanding-alerts.md`
5. `docs/architecture/overview.md`
6. `docs/architecture/ai-pipeline.md`
7. `docs/architecture/data-model.md`
8. `docs/architecture/decisions.md`

## Files to Modify

1. `README.md` - add link to docs/ in appropriate section
