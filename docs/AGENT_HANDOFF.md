# Agent Handoff Document

**Date:** 2025-12-23
**Last Agent Session:** Phase 4 AI Pipeline Implementation
**Git Commit:** `0c95a9f` - feat: implement Phase 4 AI Pipeline services

---

## Project Overview

AI-powered home security monitoring dashboard that processes Foscam camera uploads through RT-DETRv2 for object detection and Nemotron for contextual risk assessment.

**Tech Stack:**

- **Frontend:** React + TypeScript + Tailwind + Tremor (Vite)
- **Backend:** Python FastAPI + SQLite + Redis
- **AI:** RT-DETRv2 (object detection) + Nemotron via llama.cpp (risk reasoning)
- **GPU:** NVIDIA RTX A5500 (24GB)

---

## Current Status

### Completed Phases

| Phase   | Description            | Tasks | Status      |
| ------- | ---------------------- | ----- | ----------- |
| Phase 1 | Project Setup          | 7     | ✅ Complete |
| Phase 2 | Database & Layout      | 6     | ✅ Complete |
| Phase 3 | Core APIs & Components | 11    | ✅ Complete |
| Phase 4 | AI Pipeline            | 13    | ✅ Complete |

### Remaining Phases

| Phase   | Description          | Tasks | Status         |
| ------- | -------------------- | ----- | -------------- |
| Phase 5 | Events & Real-time   | 9     | 🔲 Not Started |
| Phase 6 | Dashboard Components | 7     | 🔲 Not Started |
| Phase 7 | Pages & Modals       | 6     | 🔲 Not Started |
| Phase 8 | Integration & E2E    | 8     | 🔲 Not Started |

### Test Coverage

- **Backend:** 335 tests, 98.54% coverage
- **Frontend:** 233 tests, 98.95% coverage
- **Total:** 568 tests passing

---

## How to Continue

### 1. Check Available Work

```bash
# See all ready tasks
bd ready

# List tasks for a specific phase
bd list --label phase-5
bd list --label phase-6
```

### 2. Claim and Work on Tasks

```bash
# View task details
bd show <task-id>

# Claim a task
bd update <task-id> --status in_progress

# After implementation, close the task
bd close <task-id>
```

### 3. Run Tests Before Committing

```bash
# Activate virtual environment
source .venv/bin/activate

# Backend tests
python -m pytest backend/tests/ -v

# Frontend tests
cd frontend && npm test

# Full pre-commit validation (REQUIRED before commit)
pre-commit run --all-files
```

### 4. Commit and Push

```bash
# Stage changes
git add -A

# Commit (pre-commit hooks will run automatically)
git commit -m "feat: description of changes"

# Push to origin
git push origin main

# Sync beads issue tracker
bd sync
```

---

## Critical Rules

1. **Never bypass pre-commit hooks** - No `--no-verify` flags
2. **Maintain 95% test coverage** - Write tests for all new code
3. **Follow TDD for tasks labeled `tdd`** - Write tests first
4. **Complete phases in order** - Phase dependencies exist

---

## Phase 5: Events & Real-time (Next Phase)

### Tasks to Complete

```bash
bd list --label phase-5
```

| Task ID | Description                                  |
| ------- | -------------------------------------------- |
| 7z7.5   | Implement events API endpoints               |
| 7z7.6   | Implement detections API endpoints           |
| 7z7.9   | Implement WebSocket event channel            |
| 7z7.10  | Implement WebSocket system channel           |
| 7z7.11  | Implement GPU monitor service                |
| 7z7.12  | Implement data cleanup service               |
| 7v4     | Implement 'Fast Path' high-confidence alerts |
| 7z7.16  | Write tests for events API                   |
| 7z7.17  | Write tests for detections API               |
| 7z7.18  | Write tests for WebSocket channels           |

### Key Implementation Notes

- **Events API:** CRUD for security events, filtering by camera/risk level/date
- **Detections API:** Query detections by event, camera, or time range
- **WebSocket channels:** Real-time push of events and system status
- **GPU monitor:** Poll nvidia-smi, store stats, expose via WebSocket
- **Fast Path:** Bypass batch aggregation for high-confidence (>90%) critical detections

---

## Key Files Reference

### Backend Services (Phase 4 - Implemented)

```
backend/services/
├── file_watcher.py      # Monitors /export/foscam/{camera}/ for uploads
├── detector_client.py   # Calls RT-DETRv2 at localhost:8001
├── batch_aggregator.py  # 90s window, 30s idle timeout batching
├── nemotron_analyzer.py # Risk analysis via llama.cpp at localhost:8002
├── thumbnail_generator.py # Bounding box overlays on images
└── prompts.py           # LLM prompt templates
```

### Frontend Hooks (Phase 3 - Implemented)

```
frontend/src/hooks/
├── useWebSocket.ts      # Core WebSocket with auto-reconnect
├── useEventStream.ts    # Security event stream
└── useSystemStatus.ts   # System health stream
```

### Configuration

```
backend/core/config.py   # All settings with env var support
.env.example             # Environment variable template
```

---

## Environment Setup (If Needed)

```bash
# Backend
cd /home/msvoboda/github/nemotron-v3-home-security-intelligence
source .venv/bin/activate
pip install -r backend/requirements.txt

# Frontend
cd frontend
npm install

# AI Models (optional - for full system test)
./ai/download_models.sh
```

---

## Implementation Plan

Full implementation details are in:

- `docs/plans/2024-12-22-mvp-implementation-plan.md`

---

## Contact / Resources

- **Issue Tracker:** `bd` (beads) - syncs with `.beads/` directory
- **Project Instructions:** `CLAUDE.md` in project root
- **Git Remote:** github.com:mikesvoboda/nemotron-v3-home-security-intelligence.git

---

_Last updated: 2025-12-23 by Claude Opus 4.5_
