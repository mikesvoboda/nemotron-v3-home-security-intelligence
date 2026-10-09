# Root Directory - Agent Guide

This file is the project's **single root instruction file** (owner ruling 2026-09: one root file, `CLAUDE.md` retired). It combines codebase navigation with all operational rules. Read it before touching anything.

> **Uplevel programme in progress (2026-10).** Before you change code, tests, compose, CI or docs, read [`docs/uplevel/README.md`](docs/uplevel/README.md). It names your lane, the package you may take next, and the contract every PR follows; open PRs with `gh pr create --template uplevel.md`. Mutation testing follows [`docs/uplevel/01-mutation-policy.md`](docs/uplevel/01-mutation-policy.md).

## Purpose

This is the root directory of the **Home Security Intelligence** project - an AI-powered home security monitoring dashboard that processes Foscam camera uploads through YOLO26 for object detection and the local `ai-vlm` llama.cpp engine (VlmAnalyzer) for contextual risk assessment. (R8 S2, 2026-09-29: this line named Nemotron until the legacy LLM path was deleted - see ledger row 44 and commit `602379e2`.)

## Tech Stack

- **Frontend:** React + TypeScript + Tailwind + Tremor
- **Backend:** Python FastAPI + PostgreSQL + Redis
- **AI:** YOLO26 (object detection) + the `ai-vlm` llama.cpp engine (VlmAnalyzer; risk reasoning — model identity is config, ledger D5. R8 S2 retired the Nemotron path, 2026-09-29)
- **GPU:** NVIDIA RTX A5500 (24GB)
- **Cameras:** Foscam FTP uploads to `/export/foscam/{camera_name}/`

## Quick Reference

| Resource              | Location                                                                                                                     |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Issue tracking        | [Linear](https://linear.app/nemotron-v3-home-security/team/NEM/active) (Team NEM, ID `998946a2-aa75-491b-a39d-189660131392`) |
| Linear operations     | **`/linear-python` skill only** — never call Linear MCP tools directly                                                       |
| Testing guide         | `docs/developer/testing.md`                                                                                                  |
| Git workflow guide    | `docs/developer/git-workflow.md`                                                                                             |
| Ports / env reference | `.env.example` + `docs/reference/config/env-reference.md` (authoritative runtime settings reference)                         |
| Health verification   | `/platform-healthcheck` skill                                                                                                |
| Post-MVP roadmap      | `docs/ROADMAP.md` (pursue **after Phases 1-8 are operational**)                                                              |

Feature documentation: [Multi-GPU](docs/developer/multi-gpu.md) · [Video Analytics](docs/guides/video-analytics.md) · [Zone Configuration](docs/guides/zone-configuration.md) · [Face Recognition](docs/guides/face-recognition.md)

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

This project follows **Test-Driven Development (TDD)** (tasks labeled `tdd`). Full documentation: [docs/developer/testing.md](docs/developer/testing.md).

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

Details: [docs/developer/git-workflow.md](docs/developer/git-workflow.md).

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

Everything binds `127.0.0.1` except the frontend nginx (intentionally `0.0.0.0` — it is the tunnel/Brev entry point); loopback binding is the primary security boundary. **When adding new services:** add the port variable to `.env.example` first, then reference it in docker-compose. The port tables live in **Service Ports** below; `docs/reference/config/env-reference.md` is the authoritative runtime settings reference.

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
| `.gitleaksignore`   | Gitleaks fingerprint allowlist (one measured false positive per line)               |
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
│   ├── vlm/              # The shipped LLM engine: llama.cpp `ai-vlm` container, port 8098 (R8 S2)
│   ├── gateway/          # AI Gateway: the single AI entrypoint, port 8090 (routers /yolo26
│   │                     #   + /enrich-lt only — R8 S3 pruned the florence/clip/enrichment
│   │                     #   router mounts; see Service Ports below)
│   ├── triton/           # Triton client + model repository
│   ├── common/           # Reusable TensorRT inference infrastructure
│   └── shared/           # Shared utility modules (gpu_profiler)
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
├── data/                 # Runtime data home (runtime subdirs gitignored — logs/, certs/, calibration/, profiles/; eval/benchmark/synthetic content tracked)
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
│   ├── developer/        # Developer-focused documentation (testing, git, quality)
│   ├── discoveries/      # Incident post-mortem notes (the NEM-tagged set moved to docs/archive/ in 7fba36a6)
│   ├── getting-started/  # Installation and first-run guides
│   ├── guides/           # Feature guides (video analytics, zones, faces)
│   ├── images/           # Visual assets (mockups, diagrams)
│   ├── operations/       # Operational runbooks for production
│   ├── operator/         # Operator-focused documentation (admin, deployment, monitoring)
│   ├── performance/      # Performance analyses
│   ├── plans/            # Design and implementation plans
│   ├── reference/        # Reference docs (config, troubleshooting, benchmarks)
│   ├── research/         # Numbered research studies
│   ├── testing/          # Pointer stub — living testing docs are in developer/
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
│   │   ├── stores/       # Zustand stores (dashboard, settings, metrics, workers, alerts, rate-limits, storage)
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
├── synthbench/           # Synthetic benchmark generation (see synthbench/AGENTS.md)
│   ├── generate/         # Durable stack: pinned weights, GPU window, ComfyUI renderer
│   ├── contract/         # Event contract: spec/truth/provenance models, append-only corpus store
│   ├── taxonomy/         # Committed Tier B taxonomy YAML and the seeded quota sampler
│   └── spikes/           # Throwaway harnesses (p1_bakeoff: the P1 model bake-off)
├── tests/                # Root-level test suites (benchmark, load, smoke)
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
- **Risk scoring:** LLM-determined (the `ai-vlm` llama.cpp engine — VlmAnalyzer — analyzes detections and assigns 0-100 score; the Nemotron path retired in R8 S2, 2026-09-29)
- **Batch processing:** 90-second time windows with 30-second idle timeout (`batch_window_seconds` / `batch_idle_timeout_seconds` defaults in `backend/core/config.py`)
- **Auth model:** Single-user, one switch: `EXPOSE_LAN` (OD-12). First-time admin registration required — `SetupGuardMiddleware` returns 503 for all non-whitelisted requests until the first user exists (`backend/api/middleware/setup_guard.py`). **`EXPOSE_LAN` unset (default):** no credential is required; after `O1.6` the frontend binds to `127.0.0.1` and that binding is the security boundary (until then nginx publishes `0.0.0.0:8444` and `0.0.0.0:8080`). **`EXPOSE_LAN=true`** (the LAN, a tunnel or a port forward reaches the UI): `AuthMiddleware` (`backend/api/middleware/auth.py`), the outermost middleware, refuses every HTTP request and WebSocket without the login session cookie (`session_id` from `POST /api/auth/login`, kept in Redis) or an `API_KEYS` key — `401`, or WebSocket close `4001` — except the exact paths in its `OPEN_PATHS` (health probes, setup, login, logout). Monitoring needs a credential too (UR-33; `O1.11` gives Prometheus, Alertmanager and Grafana one). `GET /api/auth/setup-status` reports `auth_required`. Per-route guards (`verify_api_key`, `require_admin_access`, `get_current_admin_user`) still apply in both modes. A new route needs no auth wiring: the gate covers it, and `backend/tests/unit/api/test_expose_lan_routes.py` proves it for every mounted route.
- **Retention:** 30 days (`retention_days` default)
- **Deployment:** Fully containerized (Podman) with GPU passthrough for AI models

## Data Flow

1. Cameras FTP upload images/videos to `/export/foscam/{camera_name}/`
2. File watcher detects new files and enqueues jobs (file paths) to the Redis detection queue — shipped streams mode writes `detections:stream` (`backend/services/redis_streams.py:73`); `detection_queue` is the legacy list name and the admin UI label (`backend/api/routes/admin.py:1264`)
3. A detection worker runs YOLO26 (ai-gateway `/yolo26`); detection IDs accumulate in Redis batch lists (`batch:{batch_id}:detections`) and closed batches are pushed to the analysis queue (`analysis:stream` in streams mode, `backend/services/redis_streams.py:873`)
4. Every 90 seconds (or 30s idle), batch sent to the `ai-vlm` VlmAnalyzer for risk assessment
5. Results stored in PostgreSQL, pushed to dashboard via WebSocket

## Entry Points for Agents

### Starting Point

1. **Read this file (AGENTS.md)** — the single root instruction file; `CLAUDE.md` was deliberately retired (owner ruling 2026-09), don't look for it
2. **Check available work:** Visit [Linear Active](https://linear.app/nemotron-v3-home-security/team/NEM/active) or filter by phase label
3. **Review docs/ROADMAP.md** - Post-MVP roadmap ideas (pursue **after Phases 1-8 are operational**)
4. **Read the AGENTS.md of any directory before exploring it** — the surviving set is the boundary list in `.agents-md-validator.yml` (W3.1 pruned the per-directory satellites; where a deleted guide's knowledge went is named in the appendix at the end of this file)

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

Host ports come from `.env` (defaults shown below are from `.env.example`); `docs/reference/config/env-reference.md` is the authoritative reference for the backend settings vars (it does not document the monitoring-stack port vars below — those live in `.env.example` and `docs/developer/PORT_STANDARDIZATION.md`). `docker-compose.prod.yml` defines 21 services; 19 start by default — vLLM (profile `vllm`) and dcgm-exporter (profile `gpu-rootful`) are opt-in.

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

| Service              | Host Port | Description                                                                                              |
| -------------------- | --------- | -------------------------------------------------------------------------------------------------------- |
| AI Gateway           | 8090      | Single AI entrypoint (Triton); routers `/yolo26` + `/enrich-lt` only (the rest were deleted, R8 S3)      |
| AI Gateway metrics   | 8002      | Gateway Prometheus metrics (`AI_GATEWAY_METRICS_PORT`)                                                   |
| vLLM (optional)      | 8097      | LLM benchmark harness (NEM-5441) — compose profile `vllm`, off by default                                |
| VLM llama.cpp engine | 8098      | `ai-vlm` llama.cpp engine (VlmAnalyzer; model identity is config, ledger D5), in the default compose set |

Since commit bc7d6101 production has **no standalone YOLO26/Florence/CLIP/enrichment containers**. `YOLO26_PORT=8095` and `LLM_PORT=8091` (the retired `ai-llm` service's port) are the only ones of these values still in `.env.example` (dev stand-ins with no prod-compose consumer — `YOLO26_PORT` is read by `ai/start_detector.sh`); `FLORENCE_PORT`, `CLIP_PORT`, `ENRICHMENT_PORT` and `ENRICHMENT_LIGHT_PORT` were removed from `.env.example` in the R8 residue sweep (`e40d69f5`). The `JAEGER_*` and `ELASTICSEARCH_*` port vars were removed — tracing is Grafana Tempo (NEM-5545) on `TEMPO_PORT=3200`, and Tempo is self-contained (no Jaeger/Elasticsearch storage backend).

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

> **Frontend Port Note:** In production (`docker-compose.prod.yml`) the nginx container publishes host 8444 → internal 8443 (HTTPS) and host 8080 → internal 8080 (plain HTTP for Cloudflare tunnel / Brev secure link), both bound to 0.0.0.0. SSL is `false` in the compose default but `setup.py` writes `SSL_ENABLED=true` into the `.env` it generates. In local development (`npm run dev`) Vite binds port **8444** (strictPort) with `https: true` (`frontend/vite.config.ts`) — but Vite 7 no longer generates a cert itself, so the handshake fails until you add a cert provider (e.g. `@vitejs/plugin-basic-ssl`) or supply `server.https` key/cert paths. `FRONTEND_PORT=5173` in `.env.example` is no longer referenced by any prod compose port mapping; only the legacy `dev` target of `frontend/Dockerfile` still runs Vite on 5173.

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
- **Runtime Config:** `docs/reference/config/env-reference.md` (authoritative reference for backend settings vars)
- **Coverage Reports:** `coverage/backend/index.html` and `frontend/coverage/index.html`
- **Feature Guides:** [Multi-GPU](docs/developer/multi-gpu.md) · [Video Analytics](docs/guides/video-analytics.md) · [Zone Configuration](docs/guides/zone-configuration.md) · [Face Recognition](docs/guides/face-recognition.md)

## Per-area rules (W3.1 appendix, batch 5)

What the six deleted single-directory guides (tests, tests/benchmark, tests/load,
data, docker, archive/vsftpd) knew that the tree does not show. Facts here were
re-verified against the code at this commit.

### tests/ — the suites CI never collects

pyproject `testpaths` is `backend/tests`, `ai/*/tests`, `ai/*/test_*.py`,
`setup_lib/tests` — **nothing under root `tests/` runs in CI**. A green local run
here gates nothing; treat these as opt-in tools, not a safety net.

- `tests/smoke/` hits a LIVE stack (backend :8000, frontend :3000, Grafana) —
  run only after `docker compose up`; env overrides `BACKEND_URL`/`FRONTEND_URL`.
- The retired root `test_setup.py` / `test_setup_core.py` live in `archive/`;
  setup coverage is in `backend/tests/unit/` — do not recreate a root tests/unit/.

### tests/benchmark/ — the `scripts/benchmark/` module tests

Counts at this head: test_quality 42, test_compare 33, test_engine_comparison 44,
test_load_test 29 — 144 pass, 4 fail **by design**: the wall-clock pacing tests
(`TestSustainedLoadBehavior`, `TestPriorityQueueMeasurement`, the sustained
runner in `TestLoadTestRunner`) exceed the pyproject global `timeout = 5`. That
red set is expected on any host; the other 144 are deterministic. MAE thresholds:
±5 acceptable, ±10 marginal. Ground-truth format and class maps: read the test
files — they are the inventory.

### tests/load/ — k6 against the live API

Runner is `scripts/load-test.sh <suite> <profile>`; suites events/cameras/
websocket/mutations/all (all.js weights: 35% events, 30% cameras). Profiles:
smoke 1 VU/10s, average 10/2min, stress 100/5min, spike 5→100→5, soak 30/10min+.
**The thresholds the old guide printed are not what ships:** `tests/load/config.js`
is CI-tuned and far looser — p95 < 2000 ms, avg < 1000 ms, `http_req_failed`
rate < 0.60 (many endpoints 503 without the AI pipeline). Trust config.js, not
remembered "p95 < 500 ms" tables. Env: `BASE_URL`, `WS_URL`, `LOAD_PROFILE`,
`API_KEY`, `ADMIN_API_KEY`.

### data/ — tracked vs runtime (the "gitignored" trap)

`git ls-files data/` = 1,409 files. **Tracked:** synthetic/ (1,283 eval fixtures —
only its media/screenshot paths are ignored), benchmark/ (101),
ai-pipeline-evaluation/ (17), external/ (6), certs/ (kept by .gitkeep; contents
ignored via the repo-wide `*.pem` rule). **Runtime, untracked:** logs/,
profiles/, clips/, thumbnails/, transcoded/ — kept unbackticked on purpose: the
gate resolves backticked dirs and these exist only after a run. profiles/ is
ignored ONLY as data/profiles/ (`.gitignore:107`) — a top-level profiles/ is NOT
ignored. The DB is PostgreSQL via `DATABASE_URL` (default name home_security per
`setup_lib/credentials.py`); tables auto-create at startup
(`backend/core/database.py` `create_all`); retention 30d through
`backend/services/cleanup_service.py` reading `settings.retention_days`. No
SQLite file ships here anymore. The alembic workflow the old guide described does
not exist in this repo — schema change = models + startup create.

### docker/ — two images, one consumer

- `docker/base.Dockerfile` — shared container base.
- `docker/python-freethreaded/` — Python 3.14 `--disable-gil`, published by
  `.github/workflows/python-freethreaded.yml` weekly (Mon 03:00 UTC) as
  `ghcr.io/mikesvoboda/python:3.14t-slim-bookworm`; bumped by editing the
  Dockerfile's `PYTHON_VERSION` + `PYTHON_SHA256`. No compose service consumes
  the 3.14t tag today — `backend/Dockerfile` carries it as a commented
  alternative base; verify GIL-off with
  `python -c "import sysconfig; print(bool(sysconfig.get_config_var('Py_GIL_DISABLED')))"`.

### archive/vsftpd/ — retired, but its port still matters

The FTP container config is archived; **no compose file defines a vsftpd service
anymore** (the old guide's `docker-compose.prod.yml` cite was dead). The
consumer side is live: `FileWatcher` (wired in `backend/main.py` :938) watches
`settings.foscam_base_path`, default `/export/foscam` — camera uploads arriving
there are still ingested. If FTP ingest is ever revived, the archive is the
starting config; until then treat it as reference only.
