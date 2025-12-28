# Root Directory - Agent Guide

## Purpose

This is the root directory of the **Home Security Intelligence** project - an AI-powered home security monitoring dashboard that processes Foscam camera uploads through RT-DETRv2 for object detection and Nemotron for contextual risk assessment.

## Tech Stack

- **Frontend:** React + TypeScript + Tailwind + Tremor
- **Backend:** Python FastAPI + PostgreSQL + Redis
- **AI:** RT-DETRv2 (object detection) + Nemotron via llama.cpp (risk reasoning)
- **GPU:** NVIDIA RTX A5500 (24GB)
- **Cameras:** Foscam FTP uploads to `/export/foscam/{camera_name}/`

## Project Status

- **Phase 1-5:** COMPLETE (Setup, Database, Core APIs, AI Pipeline, Events & Real-time)
- **Phase 6:** IN PROGRESS (Dashboard Components - Risk gauge, camera grid, activity feed)
- **Phase 7-8:** PENDING (Pages & Modals, Integration & E2E)
- **Test Coverage:** Backend 98.54% (335 tests), Frontend 98.95% (233 tests)
- **Last Updated:** 2025-12-27

## Key Files in Root

### Agent Instructions

- **AGENTS.md** (this file) - Quick reference for AI agents
- **CLAUDE.md** - Comprehensive Claude Code instructions with project overview, phase execution order, TDD approach, testing requirements, and git rules
- **docs/ROADMAP.md** - Post-MVP roadmap ideas to pursue **after Phases 1-8 are operational**

### Configuration Files

- **pyproject.toml** - Python project config with Ruff, mypy, pytest, and coverage settings
- **pytest.ini** - Pytest configuration (asyncio mode, markers for unit/integration tests)
- **.pre-commit-config.yaml** - Pre-commit hooks (ruff, mypy, eslint, prettier, typescript check, fast tests)
- **.coveragerc** - Coverage.py configuration (fail_under=90%)
- **docker-compose.yml** - Development Docker services (backend, redis, frontend) with health checks
- **docker-compose.prod.yml** - Production Docker services with multi-stage builds, resource limits, and security hardening
- **.env.example** - Environment variable template
- **README.md** - Project overview and quick start guide
- **DOCKER_QUICKSTART.md** - Quick reference for Docker commands

### Build/Dependency Files

- **uv.lock** - UV package manager lockfile
- **backend/requirements.txt** - Python dependencies
- **frontend/package.json** - Node.js dependencies

### Git Configuration

- **.gitignore** - Git ignore rules (node_modules, .venv, .env, .db files, AI model weights, coverage)
- **.gitattributes** - Git attributes

## Directory Structure

```
/Users/msvoboda/github/home_security_intelligence/
├── backend/              # FastAPI backend (Python)
│   ├── api/              # REST endpoints and WebSocket routes
│   ├── core/             # Database, Redis, config
│   ├── models/           # SQLAlchemy models
│   ├── services/         # Business logic (file watcher, detector, batch aggregator, etc.)
│   └── tests/            # Unit and integration tests
├── frontend/             # React dashboard (TypeScript)
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── hooks/        # Custom hooks (WebSocket, event streams)
│   │   ├── services/     # API client
│   │   └── styles/       # CSS/Tailwind
│   └── tests/            # Component and E2E tests
├── ai/                   # AI model scripts and configs
│   ├── rtdetr/           # RT-DETRv2 detection server
│   └── nemotron/         # Nemotron model files
├── docs/                 # Documentation
│   ├── ROADMAP.md        # Post-MVP roadmap ideas
│   ├── AI_SETUP.md       # AI services setup guide
│   ├── DOCKER_DEPLOYMENT.md  # Docker deployment guide
│   └── plans/            # Design and implementation plans
├── scripts/              # Development and deployment scripts
├── data/                 # Runtime data directory
└── coverage/             # Test coverage reports
```

## Issue Tracking

This project uses **bd** (beads) for issue tracking:

```bash
bd ready                    # Find available work
bd show <id>               # View task details
bd update <id> --status in_progress  # Claim work
bd close <id>              # Complete work
bd sync                    # Sync with git
```

Tasks are organized into **8 execution phases**. Complete phases in order:

```bash
bd list --label phase-1    # Project Setup (7 tasks) - COMPLETE
bd list --label phase-2    # Database & Layout (6 tasks) - COMPLETE
bd list --label phase-3    # Core APIs & Components (11 tasks) - COMPLETE
bd list --label phase-4    # AI Pipeline (13 tasks) - COMPLETE
bd list --label phase-5    # Events & Real-time (9 tasks) - COMPLETE
bd list --label phase-6    # Dashboard Components (7 tasks) - IN PROGRESS
bd list --label phase-7    # Pages & Modals (6 tasks) - PENDING
bd list --label phase-8    # Integration & E2E (8 tasks) - PENDING
```

## Development Workflow

### 1. Environment Setup

```bash
# Install dependencies and pre-commit hooks
./scripts/setup-hooks.sh

# Activate Python environment
source .venv/bin/activate
```

### 2. Running Tests

```bash
# Full test suite with coverage
./scripts/test-runner.sh

# Backend only
pytest backend/tests/ -v

# Frontend only
cd frontend && npm test

# Quick validation (linting + type checking + tests)
./scripts/validate.sh
```

### 3. Pre-commit Hooks

**CRITICAL:** Never bypass pre-commit hooks with `--no-verify`. All commits must pass:

- `ruff check` + `ruff format` - Python linting/formatting
- `mypy` - Python type checking
- `eslint` + `prettier` - TypeScript linting/formatting
- `pytest -m "not slow"` - Fast backend tests

### 4. Code Quality Standards

- **Coverage:** 90%+ required (enforced by pytest, see pyproject.toml)
- **Type Hints:** Required for all backend functions (enforced by mypy)
- **Line Length:** 100 characters (enforced by ruff)
- **Testing:** TDD approach for tasks labeled `tdd`

## Key Design Decisions

- **Risk scoring:** LLM-determined (Nemotron analyzes detections and assigns 0-100 score)
- **Batch processing:** 90-second time windows with 30-second idle timeout
- **No auth:** Single-user local deployment (MVP)
- **Retention:** 30 days
- **Deployment:** Hybrid (Docker for services, native for GPU AI models)

## Data Flow

1. Cameras FTP upload images/videos to `/export/foscam/{camera_name}/`
2. File watcher detects new files, sends to RT-DETRv2
3. Detections accumulate in Redis queue
4. Every 90 seconds (or 30s idle), batch sent to Nemotron for risk assessment
5. Results stored in PostgreSQL, pushed to dashboard via WebSocket

## Entry Points for Agents

### Starting Point

1. **Read CLAUDE.md** - Comprehensive project instructions
2. **Check available work:** `bd ready` or `bd list --label phase-6`
3. **Review docs/ROADMAP.md** - Post-MVP roadmap ideas (pursue **after Phases 1-8 are operational**)
4. **Read directory AGENTS.md files** - Navigate to specific areas using the AGENTS.md files in each directory

### Understanding the Codebase

1. **Backend:** Read `backend/core/config.py` for all settings
2. **Frontend:** Read `frontend/src/App.tsx` for app structure
3. **AI Pipeline:** Read `backend/services/` for processing logic
4. **Database:** Read `backend/models/` for schema

### Finding Information

- **API Routes:** `backend/api/routes/`
- **Tests:** `backend/tests/` (unit/ and integration/)
- **Components:** `frontend/src/components/`
- **Hooks:** `frontend/src/hooks/`
- **Design Docs:** `docs/plans/`

## Important Patterns

### Backend

- **Async/await:** All backend code uses asyncio
- **Dependency injection:** FastAPI dependencies for DB sessions
- **Type hints:** Required on all functions
- **Models:** SQLAlchemy ORM for database
- **Config:** Environment variables via pydantic Settings

### Frontend

- **Functional components:** React hooks (no class components)
- **TypeScript:** Strict mode enabled
- **Styling:** Tailwind utility classes + Tremor components
- **State:** React hooks (useState, useEffect, custom hooks)
- **API:** Centralized client in `services/api.ts`

### Testing

- **Backend:** pytest with fixtures, asyncio support
- **Frontend:** Vitest with React Testing Library
- **Coverage:** HTML reports in `coverage/` directory
- **Markers:** `@pytest.mark.unit` and `@pytest.mark.integration`

## Session Completion Workflow

Before ending a session, ALWAYS:

1. Run full test suite: `./scripts/test-runner.sh`
2. Update issue status: `bd close <id>` for completed tasks
3. Commit changes: `git add -A && git commit -m "description"`
4. Sync and push: `bd sync && git push origin main`
5. Verify: `git status` should show "up to date with origin"

## Resources

- **Git Remote:** github.com:mikesvoboda/home-security-intelligence.git
- **Issue Tracker:** bd (beads) - syncs with `.beads/` directory
- **Documentation:** `docs/` directory
- **Coverage Reports:** `coverage/backend/index.html` and `frontend/coverage/index.html`
