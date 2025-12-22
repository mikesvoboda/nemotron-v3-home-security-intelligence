# Claude Code Instructions

This project is an AI-powered home security monitoring dashboard.

## Project Overview

- **Frontend:** React + TypeScript + Tailwind + Tremor
- **Backend:** Python FastAPI + SQLite + Redis
- **AI:** RT-DETRv2 (object detection) + Nemotron via llama.cpp (risk reasoning)
- **GPU:** NVIDIA RTX A5500 (24GB)
- **Cameras:** Foscam FTP uploads to `/export/foscam/{camera_name}/`

## Issue Tracking

This project uses **bd** (beads) for issue tracking:

```bash
bd ready                    # Find available work
bd show <id>               # View task details
bd update <id> --status in_progress  # Claim work
bd close <id>              # Complete work
bd sync                    # Sync with git
```

## Task Execution Order

Tasks are organized into 8 execution phases. **Always complete earlier phases before starting later ones.**

### Phase 1: Project Setup (P0) - 7 tasks
Foundation - directory structures, Docker, environment, dependencies.
```bash
bd list --label phase-1
```

### Phase 2: Database & Layout Foundation (P1) - 6 tasks
SQLite models, Redis connection, Tailwind theme, app layout.
```bash
bd list --label phase-2
```

### Phase 3: Core APIs & Components (P2) - 11 tasks
Cameras API, system API, WebSocket hooks, API client, basic UI components.
```bash
bd list --label phase-3
```

### Phase 4: AI Pipeline (P3/P4) - 13 tasks
File watcher, RT-DETRv2 wrapper, detector client, batch aggregator, Nemotron analyzer.
```bash
bd list --label phase-4
```

### Phase 5: Events & Real-time (P4) - 9 tasks
Events API, detections API, WebSocket channels, GPU monitor, cleanup service.
```bash
bd list --label phase-5
```

### Phase 6: Dashboard Components (P3) - 7 tasks
Risk gauge, camera grid, live activity feed, GPU stats, EventCard.
```bash
bd list --label phase-6
```

### Phase 7: Pages & Modals (P4) - 6 tasks
Main dashboard, event timeline, event detail modal, settings pages.
```bash
bd list --label phase-7
```

### Phase 8: Integration & E2E (P4) - 8 tasks
Unit tests, E2E tests, deployment verification, documentation.
```bash
bd list --label phase-8
```

## TDD Approach

Tasks labeled `tdd` are test tasks that should be completed alongside their feature tasks:
```bash
bd list --label tdd
```

## Key Design Decisions

- **Risk scoring:** LLM-determined (Nemotron analyzes detections and assigns 0-100 score)
- **Batch processing:** 90-second time windows with 30-second idle timeout
- **No auth:** Single-user local deployment
- **Retention:** 30 days
- **Deployment:** Hybrid (Docker for services, native for GPU AI models)

## File Structure

```
backend/
  api/routes/          # FastAPI endpoints
  core/                # Database, Redis, config
  models/              # SQLAlchemy models
  services/            # Business logic
frontend/
  src/components/      # React components
  src/hooks/           # Custom hooks
  src/services/        # API client
ai/
  rtdetr/              # RT-DETRv2 detection server
  nemotron/            # Nemotron model files
docs/plans/            # Design and implementation docs
```

## Session Workflow

1. Check available work: `bd ready`
2. Filter by current phase: `bd list --label phase-N`
3. Claim task: `bd update <id> --status in_progress`
4. Implement following TDD (test first for `tdd` labeled tasks)
5. Close task: `bd close <id>`
6. End session: `bd sync && git push`
