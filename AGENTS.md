# Root Directory - Agent Guide

## Purpose

This is the root directory of the **Home Security Intelligence** project - an AI-powered home security monitoring dashboard that processes Foscam camera uploads through YOLO26 for object detection and Nemotron for contextual risk assessment.

## Tech Stack

- **Frontend:** React + TypeScript + Tailwind + Tremor
- **Backend:** Python FastAPI + PostgreSQL + Redis
- **AI:** YOLO26 (object detection) + Nemotron via llama.cpp (risk reasoning)
- **GPU:** NVIDIA RTX A5500 (24GB)
- **Cameras:** Foscam FTP uploads to `/export/foscam/{camera_name}/`

## Key Files in Root

### Agent Instructions

| File        | Purpose                                                                                                                                |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `AGENTS.md` | This file - quick reference for AI agents                                                                                              |
| `CLAUDE.md` | Comprehensive Claude Code instructions with project overview, phase execution order, TDD approach, testing requirements, and git rules |

### Configuration Files

| File                         | Purpose                                                                 |
| ---------------------------- | ----------------------------------------------------------------------- |
| `pyproject.toml`             | Python project config with Ruff, mypy, pytest, and coverage settings    |
| `.pre-commit-config.yaml`    | Pre-commit hooks (ruff, mypy, eslint, prettier, typescript check)       |
| `docker-compose.prod.yml`    | Production Docker services with multi-stage builds and resource limits  |
| `docker-compose.staging.yml` | Staging environment Docker configuration with staging-specific settings |
| `docker-compose.ghcr.yml`    | GitHub Container Registry Docker configuration                          |
| `docker-compose.ci.yml`      | CI-specific Docker configuration for GitHub Actions                     |
| `docker-compose.test.yml`    | Test containers (postgres-test, redis-test) for CI                      |
| `.env.example`               | Environment variable template                                           |
| `semgrep.yml`                | Semgrep security scanning configuration                                 |
| `vulture_whitelist.py`       | False positive suppressions for Vulture dead code detection             |
| `lychee.toml`                | Lychee link checker configuration                                       |
| `.prettierrc`                | Prettier code formatting configuration                                  |
| `codecov.yml`                | Codecov coverage reporting configuration                                |
| `commitlint.config.js`       | Commit message linting configuration                                    |

### Documentation

| File           | Purpose                                  |
| -------------- | ---------------------------------------- |
| `README.md`    | Project overview and quick start guide   |
| `LICENSE`      | Mozilla Public License 2.0               |
| `CHANGELOG.md` | Release history and notable changes      |
| `llms.txt`     | LLM-readable project documentation index |

> **Note:** Detailed Docker deployment documentation is in `docs/operator/deployment/`.

### Build Files

| File                | Purpose                                       |
| ------------------- | --------------------------------------------- |
| `pyproject.toml`    | Python project metadata (uv/pip dependencies) |
| `uv.lock`           | uv lockfile for reproducible Python builds    |
| `.python-version`   | Python version (3.14)                         |
| `package.json`      | Root-level Node.js configuration (minimal)    |
| `package-lock.json` | Node.js lockfile                              |
| `setup.sh`          | Interactive environment setup wrapper         |
| `setup.bat`         | Environment setup launcher (Windows)          |
| `setup.py`          | Python setup script with interactive prompts  |

### Git and Security Configuration

| File                | Purpose                                                                             |
| ------------------- | ----------------------------------------------------------------------------------- |
| `.gitignore`        | Git ignore rules (node_modules, .venv, .env, .db files, AI model weights, coverage) |
| `.gitattributes`    | Git attributes                                                                      |
| `.gitleaks.toml`    | Gitleaks secret scanning configuration                                              |
| `.semgrepignore`    | Semgrep ignore patterns                                                             |
| `.trivyignore`      | Trivy security scanner ignore patterns (with CVE review dates)                      |
| `.bandit.yml`       | Bandit Python security linter configuration                                         |
| `.bandit.baseline`  | Bandit baseline for known issues                                                    |
| `.secrets.baseline` | detect-secrets baseline file                                                        |
| `zap-rules.tsv`     | ZAP (OWASP) security scanning rules                                                 |
| `flaky_tests.txt`   | Known flaky tests list for CI retry logic                                           |

## Directory Structure

```
/
├── ai/                   # AI model scripts and configs
│   ├── yolo26/           # YOLO26 detection server (port 8095)
│   ├── nemotron/         # Nemotron LLM model files (port 8091)
│   ├── florence/         # Florence-2 dense captioning (port 8092)
│   ├── clip/             # CLIP embedding service (port 8093)
│   ├── enrichment/       # Heavy enrichment pipeline (port 8094)
│   └── enrichment-light/ # Light enrichment models (port 8096)
├── backend/              # FastAPI backend (Python)
│   ├── api/              # REST endpoints and WebSocket routes
│   │   ├── routes/       # FastAPI route handlers
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   ├── helpers/      # Route helper functions (enrichment transformers)
│   │   ├── middleware/   # HTTP middleware (auth, rate limiting, logging, security)
│   │   └── utils/        # API utility functions (field filtering)
│   ├── core/             # Database, Redis, config, metrics, logging
│   ├── models/           # SQLAlchemy ORM models
│   ├── repositories/     # Data access layer (base, camera, detection, event repos)
│   ├── services/         # Business logic (file watcher, detector, batch aggregator)
│   └── tests/            # Unit and integration tests
├── custom/               # Custom resources (test clips, configurations)
│   └── clips/            # Video clips for testing
├── certs/                # SSL certificates directory (placeholder)
├── data/                 # Runtime data directory (logs, thumbnails, gitignored)
├── docs/                 # Documentation
│   ├── api/              # API documentation and deprecation policy
│   ├── architecture/     # Technical architecture documentation
│   ├── benchmarks/       # Performance benchmarks (model-zoo)
│   ├── decisions/        # Architecture Decision Records (ADRs)
│   ├── developer/        # Developer-focused documentation
│   ├── development/      # Development workflow documentation
│   ├── getting-started/  # Installation and first-run guides
│   ├── images/           # Visual assets (mockups, diagrams)
│   ├── operator/         # Operator-focused documentation (admin, deployment, monitoring)
│   ├── plans/            # Design and implementation plans
│   ├── reference/        # Reference docs (api, config, troubleshooting)
│   ├── testing/          # Testing guides (TDD, Hypothesis, patterns)
│   └── user/             # End-user documentation
├── frontend/             # React dashboard (TypeScript)
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── config/       # Environment configuration and tour steps
│   │   ├── contexts/     # React contexts (SystemData, Toast)
│   │   ├── hooks/        # Custom hooks (WebSocket, event streams)
│   │   ├── mocks/        # MSW mock handlers for testing
│   │   ├── services/     # API client
│   │   ├── styles/       # CSS/Tailwind
│   │   ├── test/         # Test setup and configuration
│   │   ├── __tests__/    # Global test files (API contracts, matchers)
│   │   ├── test-utils/   # Test utilities (factories, renderWithProviders)
│   │   ├── types/        # TypeScript type definitions
│   │   └── utils/        # Utility functions
│   ├── tests/            # E2E and integration tests (Playwright)
│   └── public/           # Static assets (favicon, images)
├── monitoring/           # Prometheus + Grafana + Loki + Pyroscope configuration
│   ├── alloy/            # Grafana Alloy collector configuration
│   ├── grafana/          # Grafana dashboards
│   ├── loki/             # Loki log aggregation configuration
│   └── pyroscope/        # Pyroscope continuous profiling configuration
├── mutants/              # Mutation testing results (mutmut)
├── scripts/              # Development and deployment scripts
│   └── hooks/            # Git hooks (post-checkout worktree protection)
├── setup_lib/            # Python utilities for setup.py
├── tests/                # Root-level setup script tests
├── vsftpd/               # vsftpd FTP server container configuration
├── .beads/               # Legacy issue tracking data (deprecated, migrated to Linear)
├── .pids/                # PID files for dev services (backend.pid, frontend.pid)
└── .github/              # GitHub Actions workflows and configs
    ├── workflows/        # CI/CD workflows
    ├── codeql/           # CodeQL security analysis
    └── prompts/          # AI-powered code review prompts
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
# Run interactive setup (creates .env, installs dependencies, hooks)
./setup.sh

# Or install just the pre-commit hooks
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
2. File watcher detects new files, sends to YOLO26
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

| Area               | Entry Point                                      |
| ------------------ | ------------------------------------------------ |
| Backend config     | `backend/core/config.py`                         |
| Frontend app       | `frontend/src/App.tsx`                           |
| AI Pipeline        | `backend/services/`                              |
| Database schema    | `backend/models/`                                |
| Data access layer  | `backend/repositories/`                          |
| API Routes         | `backend/api/routes/`                            |
| API Middleware     | `backend/api/middleware/`                        |
| API Dependencies   | `backend/api/dependencies.py`                    |
| Exception handling | `backend/api/exception_handlers.py`              |
| Tests              | `backend/tests/` and `frontend/src/**/*.test.ts` |
| Components         | `frontend/src/components/`                       |
| Hooks              | `frontend/src/hooks/`                            |
| React Contexts     | `frontend/src/contexts/`                         |
| Frontend Config    | `frontend/src/config/`                           |
| Test Utilities     | `frontend/src/test-utils/`                       |
| API Mocks          | `frontend/src/mocks/`                            |
| Design docs        | `docs/plans/`                                    |
| API Reference      | `docs/api/`                                      |
| Getting Started    | `docs/getting-started/`                          |
| Scripts            | `scripts/`                                       |

## Important Patterns

### Backend

- **Async/await:** All backend code uses asyncio
- **Dependency injection:** FastAPI dependencies for DB sessions
- **Type hints:** Required on all functions
- **Models:** SQLAlchemy ORM for database
- **Config:** Environment variables via pydantic Settings
- **Repository pattern:** Data access layer in `backend/repositories/` for clean separation
- **API layer files:**
  - `backend/api/dependencies.py` - FastAPI dependency injection (auth, DB, pagination)
  - `backend/api/exception_handlers.py` - RFC 7807 Problem Details error responses
  - `backend/api/validators.py` - Request validation utilities
  - `backend/api/pagination.py` - Cursor and offset pagination helpers

### Frontend

- **Functional components:** React hooks (no class components)
- **TypeScript:** Strict mode enabled
- **Styling:** Tailwind utility classes + Tremor components
- **State:** React hooks (useState, useEffect, custom hooks)
- **API:** Centralized client in `frontend/src/services/api.ts`
- **Contexts:** Global state providers in `frontend/src/contexts/` (SystemData, Toast)
- **Testing infrastructure:**
  - `frontend/src/test/setup.ts` - Vitest setup and configuration
  - `frontend/src/test-utils/` - Test factories and render helpers
  - `frontend/src/mocks/` - MSW handlers for API mocking
  - `frontend/src/__tests__/` - Global test files and custom matchers

### Testing

- **Backend:** pytest with fixtures, asyncio support
- **Frontend:** Vitest with React Testing Library
- **Coverage:** HTML reports generated in a coverage directory (gitignored)
- **Markers:** `@pytest.mark.unit` and `@pytest.mark.integration`

## Service Ports

### Core Services

| Service        | Port | Description                                                      |
| -------------- | ---- | ---------------------------------------------------------------- |
| Frontend HTTP  | 5173 | React dashboard (Vite dev server locally, nginx in production)   |
| Frontend HTTPS | 8443 | React dashboard via nginx (SSL enabled by default in production) |
| Backend API    | 8000 | FastAPI REST + WebSocket                                         |
| PostgreSQL     | 5432 | Primary database                                                 |
| Redis          | 6379 | Cache and queues                                                 |

### AI Services

| Service            | Port | Description                                               |
| ------------------ | ---- | --------------------------------------------------------- |
| YOLO26             | 8095 | Object detection (container with GPU)                     |
| Nemotron           | 8091 | LLM risk analysis (container with GPU)                    |
| Florence-2         | 8092 | Dense captioning and visual understanding                 |
| CLIP               | 8093 | Entity re-identification embeddings                       |
| Enrichment (Heavy) | 8094 | Heavy transformer models (vehicle, fashion, demographics) |
| Enrichment (Light) | 8096 | Light models (pose, threat, reid, pet, depth)             |

### Monitoring Stack

| Service      | Port  | Description                |
| ------------ | ----- | -------------------------- |
| Grafana      | 3002  | Monitoring dashboards      |
| Prometheus   | 9090  | Metrics collection         |
| Jaeger       | 16686 | Distributed tracing UI     |
| Alertmanager | 9093  | Alert routing and delivery |
| Loki         | 3100  | Log aggregation            |
| Pyroscope    | 4040  | Continuous profiling       |
| Alloy        | 12345 | Log/metrics collector      |

> **Frontend Port Note:** In production (`docker-compose.prod.yml`), nginx serves the built React app. HTTP on host port 5173 (internal 8080), HTTPS on host port 8443 (internal 8443). SSL is enabled by default with auto-generated self-signed certificates. In local development (`npm run dev`), Vite runs directly on port 5173.

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
- **Runtime Config:** `docs/reference/config/env-reference.md` (authoritative port/env reference)
- **Coverage Reports:** `coverage/backend/index.html` and `frontend/coverage/index.html`
