# Documentation Restructure Design

> Comprehensive documentation overhaul for all audiences: end users, self-hosters, and developers.

**Date:** 2025-12-30
**Status:** Approved
**Execution:** Parallel subagents with validation

---

## Overview

Full restructure of project documentation to reflect current codebase state, with:

- Source code linking (file:symbol:line format)
- Vertical-optimized Mermaid/PlantUML diagrams
- Nano Banana Pro image generation prompts
- YAML frontmatter validation contracts
- Parallel subagent execution

## Target Audiences

| Audience         | Needs                              | Primary Docs                                |
| ---------------- | ---------------------------------- | ------------------------------------------- |
| **End users**    | Dashboard features, alerts, search | user-guide/                                 |
| **Self-hosters** | Setup, deployment, configuration   | getting-started/, admin-guide/              |
| **Developers**   | Architecture, API, contributing    | architecture/, api-reference/, development/ |

---

## New Documentation Structure

```
README.md                          # Slim: tagline, 60-sec quickstart, badges, links
docs/
├── README.md                      # Navigation hub
├── getting-started/
│   ├── prerequisites.md           # Hardware, software, GPU requirements
│   ├── installation.md            # Full setup with Podman
│   ├── first-run.md               # Verify everything works
│   └── upgrading.md               # Version migration guide
├── user-guide/
│   ├── dashboard-overview.md      # Main dashboard, risk gauge, camera grid
│   ├── event-timeline.md          # Browsing and filtering events
│   ├── search.md                  # Full-text search with filters
│   ├── alerts-notifications.md    # Alert rules, email/webhook setup
│   └── settings.md                # Camera management, processing config
├── admin-guide/
│   ├── configuration.md           # All environment variables
│   ├── storage-retention.md       # Disk management, cleanup policies
│   ├── monitoring.md              # GPU stats, health checks, DLQ
│   ├── troubleshooting.md         # Common issues and solutions
│   └── security.md                # Network isolation, hardening
├── architecture/
│   ├── overview.md                # High-level system design
│   ├── ai-pipeline.md             # Detection → Batching → Analysis flow
│   ├── data-model.md              # Database schema with relationships
│   ├── resilience.md              # Circuit breakers, retries, DLQ
│   └── real-time.md               # WebSocket channels, pub/sub
├── api-reference/
│   ├── overview.md                # Authentication, conventions, errors
│   ├── cameras.md                 # CRUD endpoints
│   ├── events.md                  # Events + search endpoints
│   ├── detections.md              # Detection endpoints
│   ├── system.md                  # Health, GPU, config, storage
│   ├── alerts.md                  # Alert rules + notifications
│   └── websocket.md               # Real-time channels
├── development/
│   ├── setup.md                   # Dev environment setup
│   ├── testing.md                 # Test strategy, running tests
│   ├── contributing.md            # PR process, code standards
│   └── patterns.md                # Key code patterns and conventions
└── images/
    ├── hero/
    ├── architecture/
    ├── user-guide/
    └── admin-guide/
```

---

## README.md Transformation

**Current:** 406 lines with embedded details
**Target:** ~100 lines, quick start only

### New README Outline

```markdown
# Home Security Intelligence

> One-line tagline + key value prop

[Hero image - Nano Banana Pro generated]

## What It Does (3 bullets max)

- Camera uploads → AI detection → Risk scoring
- 100% local, no cloud
- Real-time dashboard

## Quick Start (60 seconds)

1. Clone + setup: `./scripts/setup-hooks.sh`
2. Download models: `./ai/download_models.sh`
3. Start AI servers: `./ai/start_detector.sh` + `./ai/start_llm.sh`
4. Launch: `podman-compose up`
5. Open: http://localhost:5173

## Screenshots (3 max)

[Nano Banana Pro prompts]

## Key Features (table, links to docs)

## Documentation

→ [Full documentation](docs/README.md)

## Tech Stack (badges only)

## License

## Acknowledgments
```

### Content Migration

| Current README Section | New Location                        |
| ---------------------- | ----------------------------------- |
| Environment variables  | docs/admin-guide/configuration.md   |
| Troubleshooting        | docs/admin-guide/troubleshooting.md |
| Architecture diagrams  | docs/architecture/overview.md       |
| Database schema        | docs/architecture/data-model.md     |
| WebSocket details      | docs/api-reference/websocket.md     |
| Development commands   | docs/development/setup.md           |

---

## Source Code Linking Strategy

### Link Format

```markdown
The [BatchAggregator](../backend/services/batch_aggregator.py:45) groups detections
into 90-second windows using Redis keys defined at [line 67](../backend/services/batch_aggregator.py:67).
```

### Link Density by Doc Type

| Document Type     | Link Density | What to Link                             |
| ----------------- | ------------ | ---------------------------------------- |
| **User Guide**    | Light        | UI components only                       |
| **Admin Guide**   | Moderate     | Config classes, service files            |
| **Architecture**  | Heavy        | All services, models, key functions      |
| **API Reference** | Heavy        | Route handlers, schemas, response models |
| **Development**   | Heavy        | Test files, patterns, utilities          |

### Validation Contract (YAML Frontmatter)

```yaml
---
title: AI Pipeline Architecture
source_refs:
  - backend/services/file_watcher.py:FileWatcher:34
  - backend/services/detector_client.py:DetectorClient:21
  - backend/services/batch_aggregator.py:BatchAggregator:23
  - backend/services/nemotron_analyzer.py:NemotronAnalyzer:28
---
```

---

## Diagram Strategy (Mermaid/PlantUML)

### Vertical Optimization Rules

```markdown
# BAD: Horizontal flow (requires side-scrolling)

flowchart LR
A --> B --> C --> D --> E --> F

# GOOD: Vertical flow (natural scroll)

flowchart TB
A --> B
B --> C
C --> D
```

### Diagram Type Selection

| Concept Type        | Diagram Type                  | Orientation        |
| ------------------- | ----------------------------- | ------------------ |
| Data/process flow   | `flowchart TB`                | Top-to-bottom      |
| System architecture | `flowchart TB` with subgraphs | Vertical layers    |
| State machines      | `stateDiagram-v2`             | Vertical           |
| Sequences/timing    | `sequenceDiagram`             | Natural vertical   |
| Data models         | `erDiagram`                   | Vertical grouping  |
| Class relationships | `classDiagram`                | Vertical hierarchy |

### Visual Communication Guidelines

```yaml
diagram_guidelines:
  hierarchy:
    - Top = entry points (user actions, external triggers)
    - Middle = processing layers (services, transformations)
    - Bottom = persistence (database, storage, outputs)

  grouping:
    - Use subgraphs to cluster related components
    - Name subgraphs by responsibility, not implementation
    - Max 4-5 nodes per subgraph for readability

  flow_direction:
    - Primary flow: top-to-bottom
    - Secondary/error flows: dotted lines, right-side branches
    - Feedback loops: left-side return arrows

  visual_weight:
    - Critical path: thick lines, bold labels
    - Optional paths: dashed lines
    - Error paths: red coloring
    - Async operations: dotted lines with «async» label

  labeling:
    - Edge labels: verb phrases ("sends to", "queries", "validates")
    - Node labels: noun phrases ("Detection Queue", "Risk Analyzer")
    - Keep labels under 20 characters

  color_scheme:
    - Primary flow: default (gray/black)
    - Success states: green (#76B900)
    - Error states: red (#E74856)
    - External services: blue (#3B82F6)
    - Storage: purple (#A855F7)
```

---

## Image Generation Strategy (Nano Banana Pro)

### Aspect Ratio and Style

- **Aspect ratio:** 2:3 or 1:2 (vertical, fits GitHub markdown width)
- **Style:** Technical illustration, dark theme matching NVIDIA aesthetic (#121212 background, #76B900 accents)
- **Resolution:** 800x1200px or similar vertical format

### Prompt Template

```markdown
<!-- Nano Banana Pro Prompt:
"Technical illustration of [concept],
dark background #121212, NVIDIA green #76B900 accent lighting,
clean minimalist style, vertical 2:3 aspect ratio,
no text overlays"
-->

![Description](images/section/filename.png)
```

### Image Categories

| Category              | Usage                   | Prompt Focus                     |
| --------------------- | ----------------------- | -------------------------------- |
| **Hero images**       | README, section headers | High-level concept visualization |
| **Concept diagrams**  | Architecture docs       | Isometric technical diagrams     |
| **UI mockups**        | User guide              | Dark mode dashboard features     |
| **Status indicators** | Admin guide             | Monitoring and server concepts   |

---

## Parallel Subagent Dispatch Strategy

### Agent Assignments

| Agent       | Domain                   | Files                                    | Source Directories                                                                                    |
| ----------- | ------------------------ | ---------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **Agent 1** | README + Getting Started | `README.md`, `docs/getting-started/*.md` | `scripts/`, `ai/`, `docker-compose*.yml`                                                              |
| **Agent 2** | User Guide               | `docs/user-guide/*.md`                   | `frontend/src/components/`, `frontend/src/hooks/`                                                     |
| **Agent 3** | Admin Guide              | `docs/admin-guide/*.md`                  | `backend/core/config.py`, `backend/services/cleanup_service.py`, `backend/services/health_monitor.py` |
| **Agent 4** | Architecture             | `docs/architecture/*.md`                 | `backend/services/`, `backend/models/`, `AGENTS.md` files                                             |
| **Agent 5** | API Reference            | `docs/api-reference/*.md`                | `backend/api/routes/`, `backend/api/schemas/`                                                         |
| **Agent 6** | Development              | `docs/development/*.md`                  | `backend/tests/`, `frontend/src/__tests__/`, `.pre-commit-config.yaml`                                |

### Agent Instructions Template

Each agent receives:

1. **Domain scope** — Which docs they own
2. **Source mapping** — Key files and line numbers to reference
3. **Style guide** — Linking format, diagram rules, image prompts
4. **Validation contract** — YAML frontmatter requirements
5. **Cross-reference list** — Links to other docs they should reference

### Coordination

- `docs/README.md` (navigation hub) created LAST after all sections complete
- Each agent creates images for their domain with embedded Nano Banana Pro prompts
- Agents must use ultrathink for diagram design and visual communication

---

## Validation Strategy

### Validation Phases

| Phase       | Validator                 | Checks                                                           |
| ----------- | ------------------------- | ---------------------------------------------------------------- |
| **Phase 1** | Source Link Validator     | All `source_refs` in frontmatter exist at specified line numbers |
| **Phase 2** | Cross-Reference Validator | All internal doc links resolve                                   |
| **Phase 3** | Code Accuracy Validator   | API examples match actual signatures                             |
| **Phase 4** | Diagram Validator         | Mermaid/PlantUML syntax valid                                    |
| **Phase 5** | Completeness Validator    | All features from AGENTS.md documented                           |

### Validation Report Format

```markdown
## Documentation Validation Report

### Source References

✅ 147/150 references valid
❌ 3 broken references:

- docs/architecture/ai-pipeline.md:23 → backend/services/batch_aggregator.py:89
  Expected: `close_batch` | Found: `_close_batch_internal`

### Cross-References

✅ 52/52 internal links valid

### API Accuracy

✅ 28/30 endpoints match

### Diagrams

✅ 18/18 Mermaid diagrams render

### Coverage

✅ 94% feature coverage
```

---

## Source Reference Index

### Core Pipeline Services

```yaml
file_watcher:
  file: backend/services/file_watcher.py
  class: FileWatcher
  key_methods:
    - start
    - stop
    - _handle_file_event

dedupe:
  file: backend/services/dedupe.py
  class: DedupeService
  key_methods:
    - is_duplicate
    - mark_processed
    - compute_file_hash

detector_client:
  file: backend/services/detector_client.py
  class: DetectorClient
  key_methods:
    - detect_objects
    - health_check

batch_aggregator:
  file: backend/services/batch_aggregator.py
  class: BatchAggregator
  key_methods:
    - add_detection
    - check_batch_timeouts
    - close_batch

nemotron_analyzer:
  file: backend/services/nemotron_analyzer.py
  class: NemotronAnalyzer
  key_methods:
    - analyze_batch
    - analyze_detection_fast_path
    - health_check
```

### Frontend Components

```yaml
search:
  files:
    - frontend/src/components/search/SearchBar.tsx
    - frontend/src/components/search/SearchResultCard.tsx
    - frontend/src/components/search/SearchResultsPanel.tsx

settings:
  files:
    - frontend/src/components/settings/SettingsPage.tsx
    - frontend/src/components/settings/CamerasSettings.tsx
    - frontend/src/components/settings/ProcessingSettings.tsx
    - frontend/src/components/settings/AIModelsSettings.tsx
    - frontend/src/components/settings/DlqMonitor.tsx
    - frontend/src/components/settings/NotificationSettings.tsx
    - frontend/src/components/settings/StorageDashboard.tsx

hooks:
  files:
    - frontend/src/hooks/useWebSocket.ts
    - frontend/src/hooks/useEventStream.ts
    - frontend/src/hooks/useSystemStatus.ts
    - frontend/src/hooks/useGpuHistory.ts
    - frontend/src/hooks/useHealthStatus.ts
    - frontend/src/hooks/useStorageStats.ts
```

### API Routes

```yaml
cameras:
  file: backend/api/routes/cameras.py

events:
  file: backend/api/routes/events.py

detections:
  file: backend/api/routes/detections.py

system:
  file: backend/api/routes/system.py

alerts:
  file: backend/api/routes/alerts.py

notifications:
  file: backend/api/routes/notifications.py
```

### Infrastructure Services

```yaml
circuit_breaker:
  file: backend/services/circuit_breaker.py
  class: CircuitBreaker

retry_handler:
  file: backend/services/retry_handler.py
  class: RetryHandler

health_monitor:
  file: backend/services/health_monitor.py
  class: ServiceHealthMonitor

cleanup_service:
  file: backend/services/cleanup_service.py
  class: CleanupService

alert_engine:
  file: backend/services/alert_engine.py
  class: AlertRuleEngine

notification:
  file: backend/services/notification.py
```

---

## Deliverables Summary

### New/Modified Files

| Category        | Count  | Files                       |
| --------------- | ------ | --------------------------- |
| README          | 1      | `README.md` (rewritten)     |
| Getting Started | 4      | `docs/getting-started/*.md` |
| User Guide      | 5      | `docs/user-guide/*.md`      |
| Admin Guide     | 5      | `docs/admin-guide/*.md`     |
| Architecture    | 5      | `docs/architecture/*.md`    |
| API Reference   | 7      | `docs/api-reference/*.md`   |
| Development     | 4      | `docs/development/*.md`     |
| Navigation      | 1      | `docs/README.md` (updated)  |
| **Total**       | **32** |                             |

### Removed/Archived

- Redundant content from old README (moved to appropriate docs)
- Outdated standalone docs (content migrated)

---

## Execution Plan

1. **Dispatch 6 parallel subagents** with domain assignments
2. **Each agent ultrathinks** on diagrams and visual communication
3. **Agents produce files** with YAML frontmatter validation contracts
4. **Coordinating agent** creates `docs/README.md` navigation hub
5. **Validation agent** runs all 5 validation phases
6. **Fix any issues** identified by validation
7. **Single PR** with all changes (big bang)

---

## Acceptance Criteria

- [ ] All 32 documentation files created
- [ ] README.md reduced to ~100 lines
- [ ] All source references validate against codebase
- [ ] All internal links resolve
- [ ] All Mermaid diagrams render in GitHub
- [ ] Nano Banana Pro prompts embedded for all images
- [ ] 100% feature coverage from AGENTS.md files
- [ ] Validation report shows all checks passing
