# Root Directory - Agent Guide

## Purpose

This is the root directory of the **Home Security Intelligence** project - an AI-powered home security monitoring dashboard that processes Foscam camera uploads through RT-DETRv2 for object detection and Nemotron for contextual risk assessment.

## Tech Stack

- **Frontend:** React + TypeScript + Tailwind + Tremor
- **Backend:** Python FastAPI + PostgreSQL + Redis
- **AI:** RT-DETRv2 (object detection) + Nemotron via llama.cpp (risk reasoning)
- **GPU:** NVIDIA RTX A5500 (24GB)
- **Cameras:** Foscam FTP uploads to `/export/foscam/{camera_name}/`

## Key Files in Root

### Agent Instructions

| File        | Purpose                                                                                                                                |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `AGENTS.md` | This file - quick reference for AI agents                                                                                              |
| `CLAUDE.md` | Comprehensive Claude Code instructions with project overview, phase execution order, TDD approach, testing requirements, and git rules |

### Configuration Files

| File                      | Purpose                                                                   |
| ------------------------- | ------------------------------------------------------------------------- |
| `pyproject.toml`          | Python project config with Ruff, mypy, pytest, and coverage settings      |
| `pytest.ini`              | Pytest configuration (asyncio mode, markers for unit/integration tests)   |
| `.pre-commit-config.yaml` | Pre-commit hooks (ruff, mypy, eslint, prettier, typescript check)         |
| `.coveragerc`             | Coverage.py configuration                                                 |
| `docker-compose.yml`      | Development Docker services (backend, redis, frontend) with health checks |
| `docker-compose.prod.yml` | Production Docker services with multi-stage builds and resource limits    |
| `docker-compose.ghcr.yml` | GitHub Container Registry Docker configuration                            |
| `.env.example`            | Environment variable template                                             |
| `semgrep.yml`             | Semgrep security scanning configuration                                   |

### Documentation

| File        | Purpose                                |
| ----------- | -------------------------------------- |
| `README.md` | Project overview and quick start guide |
| `LICENSE`   | Mozilla Public License 2.0             |

> **Note:** Detailed Docker deployment documentation is in `docs/DOCKER_DEPLOYMENT.md`.

### Build Files

| File                | Purpose                                    |
| ------------------- | ------------------------------------------ |
| `package.json`      | Root-level Node.js configuration (minimal) |
| `package-lock.json` | Node.js lockfile                           |

### Git Configuration

| File             | Purpose                                                                             |
| ---------------- | ----------------------------------------------------------------------------------- |
| `.gitignore`     | Git ignore rules (node_modules, .venv, .env, .db files, AI model weights, coverage) |
| `.gitattributes` | Git attributes                                                                      |
| `.gitleaks.toml` | Gitleaks secret scanning configuration                                              |
| `.semgrepignore` | Semgrep ignore patterns                                                             |
| `.trivyignore`   | Trivy security scanner ignore patterns                                              |

## Directory Structure

```
/
├── ai/                   # AI model scripts and configs
│   ├── rtdetr/           # RT-DETRv2 detection server
│   └── nemotron/         # Nemotron model files
├── backend/              # FastAPI backend (Python)
│   ├── alembic/          # Database migrations (PostgreSQL)
│   ├── api/              # REST endpoints and WebSocket routes
│   │   ├── routes/       # FastAPI route handlers
│   │   └── schemas/      # Pydantic request/response schemas
│   ├── core/             # Database, Redis, config
│   ├── models/           # SQLAlchemy ORM models
│   ├── services/         # Business logic (file watcher, detector, batch aggregator)
│   └── tests/            # Unit and integration tests
├── data/                 # Runtime data directory
│   ├── logs/             # Application log files
│   └── thumbnails/       # Generated image thumbnails
├── docs/                 # Documentation
│   ├── architecture/     # Technical architecture documentation
│   ├── user-guide/       # End-user documentation
│   ├── plans/            # Design and implementation plans
│   ├── decisions/        # Architecture Decision Records (ADRs)
│   └── images/           # Visual assets (mockups, diagrams)
├── frontend/             # React dashboard (TypeScript)
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── hooks/        # Custom hooks (WebSocket, event streams)
│   │   ├── services/     # API client
│   │   └── styles/       # CSS/Tailwind
│   └── tests/            # Component and E2E tests
├── monitoring/           # Prometheus + Grafana configuration
│   └── grafana/          # Grafana dashboards
├── scripts/              # Development and deployment scripts
├── .beads/               # Legacy issue tracking data (deprecated)
└── .github/              # GitHub Actions workflows and configs
    ├── workflows/        # CI/CD workflows
    ├── codeql/           # CodeQL security analysis
    └── prompts/          # GitHub Copilot prompts
```

## Issue Tracking

This project uses **Linear** for issue tracking:

- **Workspace:** [nemotron-v3-home-security](https://linear.app/nemotron-v3-home-security)
- **Team:** NEM
- **Issue format:** NEM-123

```bash
# Find available work
# Visit: https://linear.app/nemotron-v3-home-security/team/NEM/active

# Filter by phase (e.g., phase-3)
# Visit: https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-3

# View and manage tasks via Linear web interface or MCP tools:
# - mcp__linear__list_issues(teamId="998946a2-aa75-491b-a39d-189660131392")
# - mcp__linear__get_issue(issueId="NEM-123")
# - mcp__linear__update_issue(issueId="NEM-123", status="<UUID>")
```

Tasks are organized into **8 execution phases**. Complete phases in order:

| Phase   | Description            | Linear Filter                                                               |
| ------- | ---------------------- | --------------------------------------------------------------------------- |
| phase-1 | Project Setup          | [View](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-1) |
| phase-2 | Database & Layout      | [View](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-2) |
| phase-3 | Core APIs & Components | [View](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-3) |
| phase-4 | AI Pipeline            | [View](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-4) |
| phase-5 | Events & Real-time     | [View](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-5) |
| phase-6 | Dashboard Components   | [View](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-6) |
| phase-7 | Pages & Modals         | [View](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-7) |
| phase-8 | Integration & E2E      | [View](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-8) |

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

### 4. Code Quality Standards

- **Coverage:** 93%+ required for unit tests (enforced by pytest)
- **Type Hints:** Required for all backend functions (enforced by mypy)
- **Line Length:** 100 characters (enforced by ruff)
- **Testing:** TDD approach for tasks labeled `tdd`

## Key Design Decisions

- **Database:** PostgreSQL (migrated from SQLite for concurrent write support)
- **Risk scoring:** LLM-determined (Nemotron analyzes detections and assigns 0-100 score)
- **Batch processing:** 90-second time windows with 30-second idle timeout
- **No auth:** Single-user local deployment (MVP)
- **Retention:** 30 days
- **Deployment:** Fully containerized (Podman) with GPU passthrough for AI models

## Data Flow

1. Cameras FTP upload images/videos to `/export/foscam/{camera_name}/`
2. File watcher detects new files, sends to RT-DETRv2
3. Detections accumulate in Redis queue
4. Every 90 seconds (or 30s idle), batch sent to Nemotron for risk assessment
5. Results stored in PostgreSQL, pushed to dashboard via WebSocket

## Entry Points for Agents

### Starting Point

1. **Read CLAUDE.md** - Comprehensive project instructions
2. **Check available work:** Visit [Linear Active](https://linear.app/nemotron-v3-home-security/team/NEM/active) or filter by phase label
3. **Review docs/ROADMAP.md** - Post-MVP roadmap ideas (pursue **after Phases 1-8 are operational**)
4. **Read directory AGENTS.md files** - Navigate to specific areas

### Understanding the Codebase

| Area            | Entry Point                                      |
| --------------- | ------------------------------------------------ |
| Backend config  | `backend/core/config.py`                         |
| Frontend app    | `frontend/src/App.tsx`                           |
| AI Pipeline     | `backend/services/`                              |
| Database schema | `backend/models/`                                |
| API Routes      | `backend/api/routes/`                            |
| Tests           | `backend/tests/` and `frontend/src/**/*.test.ts` |
| Components      | `frontend/src/components/`                       |
| Hooks           | `frontend/src/hooks/`                            |
| Design docs     | `docs/plans/`                                    |
| Scripts         | `scripts/`                                       |

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

## Service Ports

| Service     | Port | Description                            |
| ----------- | ---- | -------------------------------------- |
| Frontend    | 5173 | Vite dev server                        |
| Backend API | 8000 | FastAPI REST + WebSocket               |
| RT-DETRv2   | 8090 | Object detection (container with GPU)  |
| Nemotron    | 8091 | LLM risk analysis (container with GPU) |
| Redis       | 6379 | Cache and queues                       |

## Session Completion Workflow

Before ending a session:

1. Run full test suite: `./scripts/test-runner.sh`
2. Update issue status: Mark completed tasks as "Done" in Linear
3. Commit changes: `git add -A && git commit -m "description"`
4. Push to remote: `git push`
5. Verify: `git status` should show clean state

## Resources

- **Issue Tracker:** [Linear](https://linear.app/nemotron-v3-home-security/team/NEM/active) (Team: NEM)
- **Documentation:** `docs/` directory
- **Runtime Config:** `docs/RUNTIME_CONFIG.md` (authoritative port/env reference)
- **Coverage Reports:** `coverage/backend/index.html` and `frontend/coverage/index.html`
