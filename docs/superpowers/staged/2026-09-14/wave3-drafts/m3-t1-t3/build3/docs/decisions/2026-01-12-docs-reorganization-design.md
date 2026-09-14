# Documentation Reorganization Design

**Date:** 2026-01-12
**Status:** Approved
**Author:** Claude + Mike Svoboda

## Summary

Reorganize `docs/` from 304 files across 23 subdirectories to a clean, hierarchical hub structure with ~100 files across 5 main directories. The root `docs/` folder will contain only `README.md` (navigation hub), `AGENTS.md` (AI navigation), and `ROADMAP.md` (project vision).

## Problem Statement

The current documentation structure has:

- 46 root-level markdown files causing clutter
- Significant duplication (3 deployment docs totaling 2,700 lines)
- 35 implementation plans with no archive strategy
- 21 API reference files that could be consolidated
- Scattered testing documentation across 4 locations
- No clear entry point for different user roles

## Target Directory Structure

```
docs/
├── README.md                    # Root navigation hub (lightweight)
├── AGENTS.md                    # AI navigation (includes index)
├── ROADMAP.md                   # Post-MVP vision
│
├── getting-started/
│   ├── README.md                # Hub: Prerequisites → Install → First run
│   ├── AGENTS.md
│   └── images/
│
├── developer/
│   ├── README.md                # Hub: Architecture, API, patterns, testing
│   ├── AGENTS.md
│   ├── architecture/
│   │   ├── README.md
│   │   └── decisions/           # ADRs (this file moves here)
│   ├── api/
│   │   ├── README.md            # Overview, auth, pagination
│   │   ├── core-resources.md    # Cameras, Events, Detections, Zones (~60 endpoints)
│   │   ├── ai-pipeline.md       # Enrichment, Analysis, Batches, Jobs (~40 endpoints)
│   │   ├── system-ops.md        # System, Health, Config, Alerts (~50 endpoints)
│   │   └── realtime.md          # WebSocket, SSE, Notifications (~20 endpoints)
│   ├── patterns/
│   │   ├── README.md            # Testing, backend patterns
│   │   ├── frontend.md
│   │   └── mutation-testing.md
│   ├── contributing/
│   │   └── README.md            # Git workflow, code quality, hooks
│   └── images/
│
├── operator/
│   ├── README.md                # Hub: Deployment, monitoring, admin
│   ├── AGENTS.md
│   ├── deployment/
│   │   └── README.md            # Docker, GPU, AI setup (consolidated)
│   ├── monitoring/
│   │   ├── README.md            # Prometheus, Grafana, health checks
│   │   └── slos.md
│   ├── admin/
│   │   ├── README.md            # Configuration, secrets, retention
│   │   └── security.md
│   └── images/
│
├── user/
│   ├── README.md                # Hub: Dashboard, alerts, features
│   ├── AGENTS.md
│   └── images/
│
└── reference/
    ├── README.md                # Hub: Glossary, env vars, troubleshooting
    ├── AGENTS.md
    └── troubleshooting/
        └── README.md
```

## Decisions

### 1. Implementation Plans

**Decision:** Delete all 35 files in `docs/plans/`
**Rationale:** Code is the source of truth. Plans served their purpose during implementation.

### 2. Hub Structure

**Decision:** Hierarchical - root README.md points to sub-hubs, each directory has its own README.md
**Rationale:** No wall of text at any level. Users navigate progressively deeper.

### 3. Top-Level Directories

**Decision:** 5 content directories based on user roles + shared reference

- `getting-started/` - Role-agnostic onboarding
- `developer/` - Building/contributing
- `operator/` - Deploying/running
- `user/` - Using the dashboard
- `reference/` - Shared lookup material

**Rationale:** Users know their role first. "Who are you?" → go to your hub.

### 4. Root-Level Files

**Decision:** Hybrid approach - migrate valuable content into hub READMEs, delete redundant/outdated
**Rationale:** Preserve value while eliminating clutter.

### 5. AGENTS.md Pattern

**Decision:** Keep AGENTS.md in each subdirectory (regenerated dynamically)
**Rationale:** AI assistants benefit from per-directory navigation.

### 6. Images

**Decision:** Distribute to respective hubs (`developer/images/`, `operator/images/`, etc.)
**Rationale:** Keep related assets together.

### 7. API Documentation

**Decision:** Consolidate 21 files into 4 domain-based guides under `developer/api/`

- `core-resources.md` - Cameras, Events, Detections, Zones, Entities (~60 endpoints)
- `ai-pipeline.md` - Enrichment, Analysis, Batches, Jobs, Calibration (~40 endpoints)
- `system-ops.md` - System, Health, Config, Alerts, Logs (~50 endpoints)
- `realtime.md` - WebSocket, SSE, Notifications (~20 endpoints)

**Rationale:** Domain grouping matches system architecture. Each guide gets Mermaid diagrams.

### 8. AGENTS_INDEX.md

**Decision:** Merge into root `docs/AGENTS.md`
**Rationale:** Single AI navigation file at docs root.

## Content Migration Map

### Files to Delete

| File                      | Reason                                |
| ------------------------- | ------------------------------------- |
| `deployment-hub.md`       | Stub, replaced by operator/README.md  |
| `SECURITY.md`             | Empty placeholder                     |
| `PEER_DEPS_CONFLICT.md`   | Stale issue-specific doc              |
| `AGENTS_INDEX.md`         | Merged into AGENTS.md                 |
| `developer-hub.md`        | Replaced by developer/README.md       |
| `operator-hub.md`         | Replaced by operator/README.md        |
| `user-hub.md`             | Replaced by user/README.md            |
| `testing-hub.md`          | Content moves to developer/patterns/  |
| `docs/plans/*` (35 files) | Code is source of truth               |
| `docs/user/`              | Already consolidated into user-guide/ |
| `docs/testing/*`          | Empty placeholders                    |

### Files to Migrate (content merged into hub READMEs)

| Source                                 | Destination                         |
| -------------------------------------- | ----------------------------------- |
| `DEPLOYMENT.md`                        | operator/deployment/README.md       |
| `DOCKER_DEPLOYMENT.md`                 | operator/deployment/README.md       |
| `DEPLOYMENT_RUNBOOK.md`                | operator/deployment/README.md       |
| `DEPLOYMENT_SAFETY_CHECKLIST.md`       | operator/deployment/README.md       |
| `DEPLOYMENT_VERIFICATION_CHECKLIST.md` | operator/deployment/README.md       |
| `DEPLOYMENT_TROUBLESHOOTING.md`        | reference/troubleshooting/README.md |
| `AI_SETUP.md`                          | operator/deployment/README.md       |
| `TESTING_GUIDE.md`                     | developer/patterns/README.md        |
| `RUNTIME_CONFIG.md`                    | reference/README.md                 |
| `UV_USAGE.md`                          | developer/contributing/README.md    |
| `DOCKER_SECRETS.md`                    | operator/admin/README.md            |
| `HEALTH_CHECK_STRATEGY.md`             | operator/monitoring/README.md       |
| `SERVICE_DEPENDENCIES.md`              | operator/deployment/README.md       |

### Files to Keep as Sub-Pages

| Source                          | Destination                            |
| ------------------------------- | -------------------------------------- |
| `ROADMAP.md`                    | Keep at docs root                      |
| `FRONTEND_PATTERNS.md`          | developer/patterns/frontend.md         |
| `MUTATION_TESTING.md`           | developer/patterns/mutation-testing.md |
| `slo-definitions.md`            | operator/monitoring/slos.md            |
| `METRICS_ENDPOINT_HARDENING.md` | operator/admin/security.md             |

## Implementation Order

```
1. Create Linear tasks (track the work)
        ↓
2. Create new directory structure (empty scaffolding)
        ↓
3. Write hub README.md files (navigation content)
        ↓
4. Migrate content from root files → hub READMEs
        ↓
5. Consolidate API docs into 4 guides
        ↓
6. Distribute images to hub directories
        ↓
7. Delete obsolete files (plans/, stubs, duplicates)
        ↓
8. Update docs/README.md (root navigation hub)
        ↓
9. Update docs/AGENTS.md (merge index, update paths)
        ↓
10. Update CLAUDE.md references
        ↓
11. Regenerate sub-directory AGENTS.md files
        ↓
12. Verify no broken links
```

## Linear Tasks

### Phase 1: Reorganization

- `docs: Create new directory structure`
- `docs: Migrate root-level files`
- `docs: Consolidate API reference into 4 guides`
- `docs: Delete obsolete content`
- `docs: Distribute images to hubs`
- `docs: Regenerate AGENTS.md files`

### Phase 2: Post-Reorganization Improvements

- `docs: Add Mermaid diagram to core-resources.md`
- `docs: Add Mermaid diagram to ai-pipeline.md`
- `docs: Add Mermaid diagram to system-ops.md`
- `docs: Add Mermaid diagram to realtime.md`
- `docs: Sync API docs with OpenAPI coverage` (151 missing endpoints)
- `docs: Update CLAUDE.md references`

## Success Metrics

- Root `docs/` contains only 3 files: README.md, AGENTS.md, ROADMAP.md
- Each hub directory has README.md + AGENTS.md
- No broken internal links
- All valuable content preserved (migrated, not lost)
- ~200+ file reduction (304 → ~100)
- Clear role-based navigation for developers, operators, and users

## Risks and Mitigation

| Risk                              | Mitigation                            |
| --------------------------------- | ------------------------------------- |
| Broken links after reorganization | Run link checker before final commit  |
| Lost content                      | Migrate content before deleting files |
| CLAUDE.md references break        | Update references as dedicated step   |
| Missing API coverage              | Create Linear tasks for OpenAPI sync  |
