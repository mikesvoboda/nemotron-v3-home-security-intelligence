# Root Directory - Agent Guide

This file is the project's **single root instruction file** (owner ruling 2026-09: one root file, `CLAUDE.md` retired). It combines codebase navigation with all operational rules. Read it before touching anything.

## Purpose

This is the root directory of the **Home Security Intelligence** project - an AI-powered home security monitoring dashboard that processes Foscam camera uploads through YOLO26 for object detection and Nemotron for contextual risk assessment.

## Tech Stack

- **Frontend:** React + TypeScript + Tailwind + Tremor
- **Backend:** Python FastAPI + PostgreSQL + Redis
- **AI:** YOLO26 (object detection) + Nemotron via llama.cpp (risk reasoning)
- **GPU:** NVIDIA RTX A5500 (24GB)
- **Cameras:** Foscam FTP uploads to `/export/foscam/{camera_name}/`

## Quick Reference

| Resource              | Location                                                                                                                     |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Issue tracking        | [Linear](https://linear.app/nemotron-v3-home-security/team/NEM/active) (Team NEM, ID `998946a2-aa75-491b-a39d-189660131392`) |
| Linear operations     | **`/linear-python` skill only** — never call Linear MCP tools directly                                                       |
| Testing guide         | `docs/development/testing.md`                                                                                                |
| Git workflow guide    | `docs/development/git-workflow.md`                                                                                           |
| Ports / env reference | `.env.example` + `docs/reference/config/env-reference.md` (authoritative runtime reference)                                  |
| Health verification   | `/platform-healthcheck` skill                                                                                                |
| Post-MVP roadmap      | `docs/ROADMAP.md` (pursue **after Phases 1-8 are operational**)                                                              |

Feature documentation: [Multi-GPU](docs/development/multi-gpu.md) · [Video Analytics](docs/guides/video-analytics.md) · [Zone Configuration](docs/guides/zone-configuration.md) · [Face Recognition](docs/guides/face-recognition.md)

## Setup

```bash
python setup.py              # First-time setup (creates .env, installs deps, writes hooks)
uv sync                      # Python deps (installs the dev dependency-group;
                             # `uv sync --extra dev` still works but is deprecated in pyproject.toml)
cd frontend && npm ci        # Frontend deps (`bun install` also works — bun.lock is tracked; CI uses npm ci)
./scripts/setup-hooks.sh     # Install pre-commit + commit-msg + pre-push hooks (or `pre-commit install`)
source .venv/bin/activate    # Activate Python environment
```

## Container Runtime & Rebuilds

This project uses **Podman** (not Docker). Use `podman` commands to inspect containers.

```bash
# List all containers with status
podman ps -a --format "table {{.Names}}\t{{.Status}}\t{{.State}}"

# View logs for a specific container
podman logs <container-name>
podman logs --tail=50 -f <container-name>   # Follow last 50 lines

# Inspect a container (config, mounts, networking)
podman inspect <container-name>

# Execute a command inside a running container
podman exec -it <container-name> /bin/sh

# Check resource usage
podman stats --no-stream

# Compose operations (uses podman-compose → docker-compose plugin)
podman compose -f docker-compose.prod.yml ps
podman compose -f docker-compose.prod.yml up -d
podman compose -f docker-compose.prod.yml down
podman compose -f docker-compose.prod.yml logs <service-name>
```

**Always use `--no-cache` when rebuilding containers** — cached layers may contain stale code:

```bash
podman compose -f docker-compose.prod.yml build --no-cache
```

Full deployment walk-through: `docs/operator/deployment/README.md`.

## Infrastructure Verification

**Always complete the verification loop after infrastructure changes.** Don't mark tasks complete until ALL checks pass.

```bash
# 1. Validate compose configuration
podman compose -f docker-compose.prod.yml config -q

# 2. Check all services are running
podman ps -a --format "table {{.Names}}\t{{.Status}}\t{{.State}}"

# 3. Verify Prometheus targets (if applicable)
curl -s localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# 4. Check API health
curl -s localhost:8000/api/system/health | jq
```

A task involving infrastructure is **only complete** when:

- [ ] All compose services show `Up` and `healthy`
- [ ] All Prometheus targets show `health: "up"`
- [ ] API health endpoint returns success
- [ ] No error logs in `podman compose -f docker-compose.prod.yml logs --tail=50`

Use the `/platform-healthcheck` skill for standardized health verification.

## Testing & Coverage Gates

This project follows **Test-Driven Development (TDD)** (tasks labeled `tdd`). Full documentation: [docs/development/testing.md](docs/development/testing.md).

| Test Type           | Gate                                                   | Command                                        |
| ------------------- | ------------------------------------------------------ | ---------------------------------------------- |
| Backend unit        | tier floor 84¹                                         | `uv run pytest backend/tests/unit/ -n auto`    |
| Backend integration | tier floor 37¹                                         | `uv run pytest backend/tests/integration/ -n0` |
| Frontend            | floors 80 / 74.6 / 78.4 / 80.9² (measured values)      | `cd frontend && npm test`                      |
| **Full validation** | **80% combined unit+integration** (the executed floor) | `./scripts/validate.sh`                        |

Gate semantics (re-verified against the tree 2026-09-22):

- The executed **absolute** backend floor is **80% on combined unit+integration**: `scripts/validate.sh` merges both tiers and checks `--fail-under=80`, mirrored in `.github/workflows/nightly-full-gate.yml`.
- `pyproject.toml` `fail_under = 85` is **not** an absolute floor. Per owner ruling A7.1 it is the PR diff gate's **relative baseline** over merged shard data; the diff gate (`scripts/check-test-coverage-gate.py`, `COVERAGE_DIFF_EPSILON_PP = 0.5`) forgives drops up to its 0.5pp noise band (WP2.5 re-derived the band from post-seed-pin runs).
- ¹ Per-tier absolute floors (unit 84, integration 37 — WP2.5 measured) are enforced in the CI merge steps **only when the tier fully passed** — a red shard means partial data, and partial data is never floor-checked (`ci.yml` unit/integration floor steps).
- ² Frontend floors are the **measured** stmts/branches/functions/lines values (R-1/WP2.3; run 35486259345), defined in `frontend/scripts/merge-shard-coverage.mjs` and enforced via `--enforce` in CI only when all Vitest shards passed.
- Reference measurement (2026-09-20): 84.12% blended / 86.02% line / 76.27% branch — three different numbers (`--format=total` is the blend). Main runs publish line and branch separately; see the testing guide.

## Git Rules

**Never bypass pre-commit hooks** (no `--no-verify`). All commits must pass `ruff check` + `ruff format`, `mypy`, and `eslint` + `prettier`; `commit-msg` runs commitlint; the `pre-push` stage runs parallel validation.

```bash
./scripts/setup-hooks.sh    # Full hook setup (pre-commit + commit-msg + pre-push)
# or manually:
pre-commit install && pre-commit install --hook-type pre-push
```

Details: [docs/development/git-workflow.md](docs/development/git-workflow.md).

## ⚠️ Network Ports — `.env` Is the Single Source of Truth

**ALL network ports MUST be defined in `.env` and referenced via environment variables in `docker-compose.prod.yml`.**

```yaml
# CORRECT - Port from .env
ports:
  - '127.0.0.1:${VLLM_PORT:-8097}:8000'

# WRONG - Hardcoded port
ports:
  - '127.0.0.1:8097:8000'
```

Everything binds `127.0.0.1` except the frontend nginx (intentionally `0.0.0.0` — it is the tunnel/Brev entry point); loopback binding is the primary security boundary. **When adding new services:** add the port variable to `.env.example` first, then reference it in docker-compose. The port tables live in **Service Ports** below; `docs/reference/config/env-reference.md` is the authoritative runtime reference.

## Key Files in Root

### Agent Instructions

| File        | Purpose                                                                                 |
| ----------- | --------------------------------------------------------------------------------------- |
| `AGENTS.md` | This file - the project's single root instruction file (navigation + operational rules) |

### Configuration Files

| File                      | Purpose                                                                |
| ------------------------- | ---------------------------------------------------------------------- |
| `pyproject.toml`          | Python project config with Ruff, mypy, pytest, and coverage settings   |
| `.pre-commit-config.yaml` | Pre-commit hooks (ruff, mypy, eslint, prettier, typescript check)      |
| `docker-compose.prod.yml` | Production Docker services with multi-stage builds and resource limits |
| `docker-compose.ghcr.yml` | Pre-built GHCR images for user deployment                              |
| `docker-compose.ci.yml`   | CI-specific Docker configuration for GitHub Actions                    |
| `docker-compose.test.yml` | Test containers (postgres-test, redis-test) for CI                     |
| `.env.example`            | Environment variable template                                          |
| `semgrep.yml`             | Semgrep security scanning configuration                                |
| `vulture_whitelist.py`    | False positive suppressions for Vulture dead code detection            |
| `lychee.toml`             | Lychee link checker configuration                                      |
| `.prettierrc`             | Prettier code formatting configuration                                 |
| `codecov.yml`             | Codecov coverage reporting configuration                               |
| `commitlint.config.js`    | Commit message linting configuration                                   |

### Documentation

| File           | Purpose                                  |
| -------------- | ---------------------------------------- |
| `README.md`    | Project overview and quick start guide   |
| `LICENSE`      | Apache License 2.0                       |
| `CHANGELOG.md` | Release history and notable changes      |
| `llms.txt`     | LLM-readable project documentation index |

> **Note:** Detailed Docker deployment documentation is in `docs/operator/deployment/`.

### Build Files

| File              | Purpose                                       |
| ----------------- | --------------------------------------------- |
| `pyproject.toml`  | Python project metadata (uv/pip dependencies) |
| `uv.lock`         | uv lockfile for reproducible Python builds    |
| `.python-version` | Python version (3.14)                         |
| `package.json`    | Root-level Node.js configuration (minimal)    |
| `setup.py`        | Python setup script with interactive prompts  |

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

## Directory Structure

```
/
├── ai/                   # AI model scripts and configs
│   ├── yolo26/           # YOLO26 detection code (prod: ai-gateway router /yolo26)
│   ├── nemotron/         # Nemotron LLM (llama.cpp container, port 8091)
│   ├── florence/         # Florence-2 dense captioning (prod: ai-gateway router /florence)
│   ├── clip/             # CLIP embeddings (prod: ai-gateway router /clip)
│   ├── enrichment/       # Heavy enrichment models (prod: ai-gateway router /enrichment)
│   ├── enrichment-light/ # Light enrichment models (prod: router /enrich-lt)
│   ├── gateway/          # AI Gateway: the single AI entrypoint, port 8090
│   └── triton/           # Triton client + model repository
├── backend/              # FastAPI backend (Python)
│   ├── api/              # REST endpoints and WebSocket routes
│   │   ├── routes/       # FastAPI route handlers
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   ├── middleware/   # HTTP middleware (auth, rate limiting, logging, security)
│   │   └── utils/        # API utility functions (field filtering)
│   ├── core/             # Database, Redis, config, metrics, logging
│   ├── models/           # SQLAlchemy ORM models
│   ├── repositories/     # Data access layer (base, camera, detection, event repos)
│   ├── services/         # Business logic (file watcher, detector, batch aggregator)
│   └── tests/            # Unit and integration tests
├── certs/                # SSL certificates directory (placeholder)
├── config/               # Runtime YAML configs (tracker configs, quality baselines)
├── data/                 # Runtime data directory (logs, thumbnails, gitignored)
├── docker/               # Shared container base images (base.Dockerfile)
├── docs/                 # Documentation (full index: docs/AGENTS.md)
│   ├── ai/               # AI model-zoo and pipeline documentation
│   ├── api/              # API documentation and deprecation policy
│   ├── architecture/     # Technical architecture documentation
│   ├── archive/          # Archived point-in-time reports and NEM investigations
│   ├── benchmarks/       # Performance benchmarks (model-zoo)
│   ├── components/       # UI component documentation
│   ├── decisions/        # Architecture Decision Records (ADRs)
│   ├── deployment/       # Container-orchestration docs (startup, health checks)
│   ├── developer/        # Developer-focused documentation
│   ├── development/      # Development workflow documentation (testing, git, quality)
│   ├── discoveries/      # NEM-tagged discovery notes
│   ├── getting-started/  # Installation and first-run guides
│   ├── guides/           # Feature guides (video analytics, zones, faces)
│   ├── images/           # Visual assets (mockups, diagrams)
│   ├── operations/       # Operational runbooks for production
│   ├── operator/         # Operator-focused documentation (admin, deployment, monitoring)
│   ├── performance/      # Performance analyses
│   ├── plans/            # Design and implementation plans
│   ├── reference/        # Reference docs (api, config, troubleshooting)
│   ├── research/         # Numbered research studies
│   ├── testing/          # Pointer stub — living testing docs are in development/
│   ├── ui/               # Page-by-page UI documentation
│   └── user/             # End-user documentation
├── frontend/             # React dashboard (TypeScript)
│   ├── src/              # App source (full index: src/AGENTS.md)
│   │   ├── components/   # React components
│   │   ├── config/       # Environment configuration and tour steps
│   │   ├── constants/    # App-wide constants
│   │   ├── contexts/     # React contexts (Auth, Camera, Health, SystemData, Theme, Toast, ...)
│   │   ├── hooks/        # Custom hooks (WebSocket, event streams)
│   │   ├── pages/        # Route-level page components
│   │   ├── mocks/        # MSW mock handlers for testing
│   │   ├── services/     # API client
│   │   ├── stores/       # Zustand stores (dashboard, settings, queues)
│   │   ├── styles/       # CSS/Tailwind
│   │   ├── test/         # Test setup and configuration
│   │   ├── __tests__/    # Global test files (API contracts, matchers)
│   │   ├── test-utils/   # Test utilities (factories, renderWithProviders)
│   │   ├── types/        # TypeScript type definitions
│   │   └── utils/        # Utility functions
│   ├── tests/            # E2E and integration tests (Playwright)
│   ├── scripts/          # Frontend build/CI helper scripts
│   └── public/           # Static assets (favicon, images)
├── env-templates/        # Hardware-profile .env templates (gb300, etc.)
├── monitoring/           # Prometheus + Grafana + Loki + Pyroscope configuration
│   ├── alloy/            # Grafana Alloy collector configuration
│   ├── cadvisor/         # cAdvisor container metrics configuration
│   ├── dcgm/             # NVIDIA DCGM GPU-exporter configuration
│   ├── grafana/          # Grafana dashboards
│   ├── loki/             # Loki log aggregation configuration
│   ├── pyroscope/        # Pyroscope continuous profiling configuration
│   └── tempo/            # Tempo trace storage configuration
├── scripts/              # Development and deployment scripts
│   ├── benchmark/        # Benchmark harness scripts
│   ├── dataset_converters/ # Training-dataset conversion scripts
│   ├── hooks/            # Git hooks (post-checkout worktree protection)
│   ├── synthetic/        # Synthetic test-data generation
│   └── validate_docs/    # Documentation validators
├── setup_lib/            # Python utilities for setup.py
├── tests/                # Root-level test suites (benchmark, load, smoke)
├── tools/                # Bundled tooling (nemo_data_designer)
├── archive/              # Not-load-bearing artifacts pending delete sign-off (see archive/README.md)
└── .github/              # GitHub Actions workflows and configs
    ├── workflows/        # CI/CD workflows
    ├── codeql/           # CodeQL security analysis
    └── prompts/          # AI-powered code review prompts
```

## Issue Tracking

This project uses **Linear** for issue tracking:

- **Workspace:** [nemotron-v3-home-security](https://linear.app/nemotron-v3-home-security)
- **Team:** NEM (ID `998946a2-aa75-491b-a39d-189660131392`), issues formatted NEM-123
- **Active board:** <https://linear.app/nemotron-v3-home-security/team/NEM/active>
- **By phase:** <https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-3> etc.

**All Linear operations go through the `/linear-python` skill only — do not call Linear MCP tools directly.** (The skill may be absent in some sandboxes; if so, say so in the final report rather than improvising MCP calls.)

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

### Code Quality Standards

- **Coverage:** see **Testing & Coverage Gates** above — executed floor is 80% combined unit+integration; `pyproject.toml` 85 is the PR diff baseline, not an absolute floor (A7.1)
- **Type Hints:** Required for all backend functions (enforced by mypy)
- **Line Length:** 100 characters (enforced by ruff)
- **Testing:** TDD approach for tasks labeled `tdd`

## Key Design Decisions

- **Database:** PostgreSQL (migrated from SQLite for concurrent write support)
- **Risk scoring:** LLM-determined (Nemotron analyzes detections and assigns 0-100 score)
- **Batch processing:** 90-second time windows with 30-second idle timeout (`batch_window_seconds` / `batch_idle_timeout_seconds` defaults in `backend/core/config.py`)
- **Auth model:** Single-user local deployment. First-time admin registration required — `SetupGuardMiddleware` returns 503 for all non-whitelisted requests until the first user exists (`backend/api/middleware/setup_guard.py`). After registration, API endpoints are open — no per-request login required. Network binding to `127.0.0.1` is the primary security boundary. Admin/destructive operations are guarded by per-route dependencies (`verify_api_key`, `require_admin_access`). The global `AuthMiddleware` class exists for future multi-user support but is **not active** (disabled per NEM-5527).
- **Retention:** 30 days (`retention_days` default)
- **Deployment:** Fully containerized (Podman) with GPU passthrough for AI models

## Data Flow

1. Cameras FTP upload images/videos to `/export/foscam/{camera_name}/`
2. File watcher detects new files, sends to YOLO26
3. Detections accumulate in Redis queue
4. Every 90 seconds (or 30s idle), batch sent to Nemotron for risk assessment
5. Results stored in PostgreSQL, pushed to dashboard via WebSocket

## Entry Points for Agents

### Starting Point

1. **Read this file (AGENTS.md)** — the single root instruction file; `CLAUDE.md` was deliberately retired (owner ruling 2026-09), don't look for it
2. **Check available work:** Visit [Linear Active](https://linear.app/nemotron-v3-home-security/team/NEM/active) or filter by phase label
3. **Review docs/ROADMAP.md** - Post-MVP roadmap ideas (pursue **after Phases 1-8 are operational**)
4. **Read the AGENTS.md of any directory before exploring it** — every code directory has one documenting purpose, key files, and patterns (`ai/AGENTS.md`, `backend/AGENTS.md`, `frontend/AGENTS.md`, `docs/AGENTS.md`, …)

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
- **Contexts:** Global state providers in `frontend/src/contexts/` (Auth, Camera, Health, SystemData, Theme, Toast and others)
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

Host ports come from `.env` (defaults shown below are from `.env.example`); `docs/reference/config/env-reference.md` is the authoritative reference. `docker-compose.prod.yml` defines 21 services; 19 start by default — vLLM (profile `vllm`) and dcgm-exporter (profile `gpu-rootful`) are opt-in.

### Core Services

| Service        | Host Port | Description                                                          |
| -------------- | --------- | -------------------------------------------------------------------- |
| Frontend HTTPS | 8444      | nginx container, internal 8443 (`FRONTEND_HTTPS_PORT`)               |
| Frontend HTTP  | 8080      | nginx container, internal 8080 — tunnel entry (`FRONTEND_HTTP_PORT`) |
| Backend API    | 8000      | FastAPI REST + WebSocket                                             |
| PostgreSQL     | 5432      | Primary database                                                     |
| Redis          | 6379      | Cache and queues                                                     |
| go2rtc API     | 1984      | Stream gateway API (`GO2RTC_API_PORT`)                               |
| go2rtc WebRTC  | 8555      | Stream gateway WebRTC (`GO2RTC_WEBRTC_PORT`)                         |

### AI Services

| Service              | Host Port | Description                                                                                         |
| -------------------- | --------- | --------------------------------------------------------------------------------------------------- |
| AI Gateway           | 8090      | Single AI entrypoint (Triton) with routers `/yolo26` `/florence` `/clip` `/enrichment` `/enrich-lt` |
| AI Gateway metrics   | 8002      | Gateway Prometheus metrics (`AI_GATEWAY_METRICS_PORT`)                                              |
| Nemotron (llama.cpp) | 8091      | LLM risk analysis container (GPU)                                                                   |
| vLLM (optional)      | 8097      | Alternative LLM engine — compose profile `vllm`, off by default                                     |

Since commit bc7d6101 production has **no standalone YOLO26/Florence/CLIP/enrichment containers**. `YOLO26_PORT=8095`, `FLORENCE_PORT=8092`, `CLIP_PORT=8093`, `ENRICHMENT_PORT=8094` and `ENRICHMENT_LIGHT_PORT=8096` in `.env.example` are legacy values kept for reference and local dev scripts only, as are the `JAEGER_*` port vars — tracing is Grafana Tempo (NEM-5545), Jaeger UI port 16686 is dead.

### Monitoring Stack

| Service           | Port  | Description                                 |
| ----------------- | ----- | ------------------------------------------- |
| Grafana           | 3002  | Monitoring dashboards (proxied at /grafana) |
| Prometheus        | 9090  | Metrics collection                          |
| Tempo             | 3200  | Distributed tracing (replaced Jaeger)       |
| Alertmanager      | 9093  | Alert routing and delivery                  |
| Loki              | 3100  | Log aggregation                             |
| Pyroscope         | 4040  | Continuous profiling                        |
| Alloy             | 12345 | Log/metrics collector UI                    |
| Node exporter     | 9100  | Host metrics                                |
| Redis exporter    | 9121  | Redis metrics                               |
| JSON exporter     | 7979  | Custom metrics                              |
| Blackbox exporter | 9115  | Endpoint probes                             |
| DCGM exporter     | 9400  | NVIDIA GPU metrics                          |

> **Frontend Port Note:** In production (`docker-compose.prod.yml`) the nginx container publishes host 8444 → internal 8443 (HTTPS) and host 8080 → internal 8080 (plain HTTP for Cloudflare tunnel / Brev secure link), both bound to 0.0.0.0. SSL is `false` in the compose default but `setup.py` writes `SSL_ENABLED=true` into the `.env` it generates. In local development (`npm run dev`) Vite serves HTTPS on port **8444** (strictPort). `FRONTEND_PORT=5173` in `.env.example` is no longer referenced by any prod compose port mapping; only the legacy `dev` target of `frontend/Dockerfile` still runs Vite on 5173.

## Session Workflow

1. Check [Linear Active](https://linear.app/nemotron-v3-home-security/team/NEM/active), claim a task (assign to yourself, set "In Progress")
2. Implement following TDD
3. Validate: `./scripts/validate.sh`

Before ending a session:

1. Run full test suite: `./scripts/test-runner.sh`
2. Update issue status: Mark completed tasks as "Done" in Linear (via `/linear-python`)
3. Commit changes: `git add -A && git commit -m "description"`
4. Push to remote: `git push`
5. Verify: `git status` should show clean state

Infrastructure work additionally requires the **Infrastructure Verification** checklist above before it counts as complete.

## Resources

- **Issue Tracker:** [Linear](https://linear.app/nemotron-v3-home-security/team/NEM/active) (Team: NEM)
- **Documentation:** `docs/` directory (index: `docs/AGENTS.md`)
- **Runtime Config:** `docs/reference/config/env-reference.md` (authoritative port/env reference)
- **Coverage Reports:** `coverage/backend/index.html` and `frontend/coverage/index.html`
- **Feature Guides:** [Multi-GPU](docs/development/multi-gpu.md) · [Video Analytics](docs/guides/video-analytics.md) · [Zone Configuration](docs/guides/zone-configuration.md) · [Face Recognition](docs/guides/face-recognition.md)
