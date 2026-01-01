# Documentation Overhaul Design

> Hub-and-spoke documentation restructure for multi-audience onboarding.

**Created:** 2025-12-31
**Status:** Approved

---

## Problem Statement

Documentation audit revealed:

- 6 critical accuracy issues causing user failures
- 50% of database models undocumented
- Three different risk score definitions across docs
- Missing backup/recovery, GPU setup, database initialization docs
- Unclear onboarding paths for different audiences
- Large monolithic docs that overwhelm readers

## Solution: Hub-and-Spoke Architecture

### Entry Point: README.md

README becomes a router with three paths:

```markdown
## Quick Start (Pick Your Path)

### I want to run this at home

→ User Hub - Setup, dashboard usage, understanding alerts

### I want to deploy and maintain this

→ Operator Hub - Installation, configuration, monitoring, backups

### I want to contribute or extend this

→ Developer Hub - Architecture, codebase tour, testing, PRs
```

### Three Hubs

Each hub links to 8-15 small, focused "spoke" documents.

**User Hub** (`docs/user-hub.md`)

- Prerequisites, installation options, first run
- Dashboard overview, risk scores, reviewing events
- Alerts, false alarms, search, settings
- ~10 spokes, non-technical language

**Operator Hub** (`docs/operator-hub.md`)

- Requirements, container setup, GPU passthrough
- Deployment options, step-by-step install
- Env vars, AI config, cameras, database
- Monitoring, backup/recovery, retention, upgrading
- ~15 spokes, technical but practical

**Developer Hub** (`docs/developer-hub.md`)

- Architecture, codebase tour, data model, AI pipeline
- Local setup, testing, pre-commit hooks
- WebSocket, alert system, video processing
- Contributing, design decisions
- ~12 spokes, deep technical content

### Shared Reference

Single source of truth, linked from all hubs:

```
docs/reference/
├── api/              # REST + WebSocket endpoints
├── config/
│   ├── env-reference.md    # All env vars, one table
│   └── risk-levels.md      # THE canonical definition
├── troubleshooting/  # Symptom-based index
└── glossary.md
```

## Document Standards

Every spoke follows this template:

```markdown
# [Topic Title]

> One-sentence summary.

**Time to read:** ~X min
**Prerequisites:** [Link or "None"]

---

[Content - 2-4 sections max]

---

## Next Steps

- → [Related Doc](path.md)
- ← Back to [Hub](../hub.md)
```

**Rules:**

- Max 400 lines per spoke
- Commands include expected output
- Warnings use `> [!WARNING]` syntax
- No orphan docs - every spoke linked from a hub

## Implementation Phases

### Phase 1: Critical Accuracy Fixes

| Fix               | File                                   | Change                                                         |
| ----------------- | -------------------------------------- | -------------------------------------------------------------- |
| Risk score ranges | Create reference/config/risk-levels.md | Canonical: Low 0-29, Medium 30-59, High 60-84, Critical 85-100 |
| Coverage badges   | README.md                              | Update to 95%/89% or make dynamic                              |
| VRAM requirements | AI docs                                | Correct to ~7GB total                                          |
| Env var names     | AI_SETUP.md                            | AI_RTDETR_PORT → RTDETR_PORT                                   |
| Docker/Podman     | prerequisites.md                       | State both supported                                           |
| Node version      | package.json                           | Add engines field                                              |

### Phase 2: Hub Structure

- Create user-hub.md, operator-hub.md, developer-hub.md
- Update README.md to router format
- Create reference/config/risk-levels.md
- Link existing docs from hubs

### Phase 3: Content Migration

- Split large docs into focused spokes
- Fill gaps: backup.md, gpu-setup.md, database.md
- Update data-model.md with all 12 models
- Document alert system, video processing

### Phase 4: Polish

- Add screenshots to key user docs
- Cross-link related spokes
- Add "Next →" navigation
- Review and test all paths

## File Structure

```
docs/
├── user-hub.md
├── operator-hub.md
├── developer-hub.md
├── user/
│   ├── prerequisites.md
│   ├── installation-options.md
│   ├── first-run.md
│   ├── dashboard-overview.md
│   ├── risk-scores.md
│   ├── reviewing-events.md
│   ├── alerts.md
│   ├── false-alarms.md
│   ├── search.md
│   ├── settings.md
│   └── faq.md
├── operator/
│   ├── requirements.md
│   ├── container-setup.md
│   ├── gpu-setup.md
│   ├── deployment-options.md
│   ├── installation.md
│   ├── env-vars.md
│   ├── ai-config.md
│   ├── cameras.md
│   ├── database.md
│   ├── monitoring.md
│   ├── backup.md
│   ├── retention.md
│   ├── performance.md
│   └── upgrading.md
├── developer/
│   ├── architecture.md
│   ├── codebase-tour.md
│   ├── data-model.md
│   ├── ai-pipeline.md
│   ├── local-setup.md
│   ├── testing.md
│   ├── hooks.md
│   ├── real-time.md
│   ├── alerts.md
│   ├── video.md
│   ├── contributing.md
│   ├── decisions.md
│   └── frontend-hooks.md
├── reference/
│   ├── api/
│   │   ├── overview.md
│   │   ├── cameras.md
│   │   ├── events.md
│   │   ├── detections.md
│   │   ├── alerts.md
│   │   ├── system.md
│   │   └── websocket.md
│   ├── config/
│   │   ├── env-reference.md
│   │   └── risk-levels.md
│   ├── troubleshooting/
│   │   ├── index.md
│   │   ├── gpu-issues.md
│   │   ├── connection-issues.md
│   │   ├── ai-issues.md
│   │   └── database-issues.md
│   └── glossary.md
└── plans/
    └── [design docs]
```

## Success Criteria

- [ ] All 6 critical accuracy issues fixed
- [ ] Three hubs created with complete navigation
- [ ] Every spoke under 400 lines
- [ ] No orphan documentation
- [ ] All paths tested: user, operator, developer
- [ ] Screenshots in key user docs
