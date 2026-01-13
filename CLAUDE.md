# Claude Code Instructions

This project is an AI-powered home security monitoring dashboard.

## Project Overview

- **Frontend:** React + TypeScript + Tailwind + Tremor
- **Backend:** Python FastAPI + PostgreSQL + Redis
- **AI:** RT-DETRv2 (object detection) + Nemotron via llama.cpp (risk reasoning)
- **GPU:** NVIDIA RTX A5500 (24GB)
- **Cameras:** Foscam FTP uploads to `/export/foscam/{camera_name}/`
- **Containers:** Docker Compose files compatible with both Docker and Podman

## Local Development Environment

**First-time setup:** Run the interactive setup script to generate `.env` and `docker-compose.override.yml`:

```bash
./setup.sh              # Quick mode - accept defaults with Enter
./setup.sh --guided     # Guided mode - step-by-step with explanations
```

This project uses standard Docker Compose files (`docker-compose.prod.yml`) that work with both Docker and Podman:

```bash
# Using Docker Compose
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml logs -f
docker compose -f docker-compose.prod.yml down

# Using Podman Compose
podman-compose -f docker-compose.prod.yml up -d
podman-compose -f docker-compose.prod.yml logs -f
podman-compose -f docker-compose.prod.yml down
```

For macOS with Podman, set the AI host:

```bash
export AI_HOST=host.containers.internal
```

## Deploy from CI/CD Containers

Pull and redeploy using pre-built containers from GitHub Container Registry (main branch):

```bash
# Pull latest containers from GHCR
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:latest
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend:latest

# Stop current containers
podman-compose -f docker-compose.prod.yml down

# Redeploy with latest images
podman-compose -f docker-compose.prod.yml up -d

# Verify deployment
curl http://localhost:8000/api/system/health/ready
```

**Note:** CI/CD automatically builds and pushes images on every merge to `main`. Use `:latest` for most recent stable build or specify a commit SHA tag for specific versions.

## Python Dependencies (uv)

This project uses **uv** for Python dependency management (10-100x faster than pip):

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or with Homebrew: brew install uv

# Sync dependencies (creates .venv if needed)
uv sync --extra dev

# Add a new dependency
uv add <package>           # Production dependency
uv add --dev <package>     # Dev dependency

# Update lock file after editing pyproject.toml
uv lock

# Run a command in the virtual environment
uv run pytest              # Run pytest
uv run ruff check backend  # Run linter
uv run mypy backend        # Run type checker

# The venv is automatically created at .venv/
# Dependencies are defined in pyproject.toml
# Lock file is uv.lock (commit this file)
```

**Key files:**

- `pyproject.toml` - Dependencies and tool configuration
- `uv.lock` - Locked dependency versions (commit this)
- `.python-version` - Python version (3.14)

### UV Version Management (CI/CD)

CI workflows pin **uv version `0.9.18`** for reproducibility. See workflow files for details.

## Issue Tracking

This project uses **Linear** for issue tracking. For detailed MCP tools, workflow state UUIDs, and usage examples, see **[Linear Integration Guide](docs/development/linear-integration.md)**.

- **Workspace:** [nemotron-v3-home-security](https://linear.app/nemotron-v3-home-security)
- **Team:** NEM
- **Team ID:** `998946a2-aa75-491b-a39d-189660131392`

## Task Execution Order

Tasks are organized into 8 execution phases. **Always complete earlier phases before starting later ones.**

| Phase | Focus                             | Link                                                                        |
| ----- | --------------------------------- | --------------------------------------------------------------------------- |
| 1     | Project Setup (P0)                | [View](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-1) |
| 2     | Database & Layout Foundation (P1) | [View](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-2) |
| 3     | Core APIs & Components (P2)       | [View](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-3) |
| 4     | AI Pipeline (P3/P4)               | [View](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-4) |
| 5     | Events & Real-time (P4)           | [View](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-5) |
| 6     | Dashboard Components (P3)         | [View](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-6) |
| 7     | Pages & Modals (P4)               | [View](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-7) |
| 8     | Integration & E2E (P4)            | [View](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-8) |

## Post-MVP Roadmap (After MVP is Operational)

After the MVP is **fully operational end-to-end** (Phases 1-8 complete, deployment verified, and tests passing), review `docs/ROADMAP.md` to identify post-MVP enhancements and create new Linear issues accordingly.

## Testing and TDD

This project follows **Test-Driven Development (TDD)** for all feature implementation. Tests drive the design and ensure correctness from the start.

**Documentation:**

- **[TDD Workflow Guide](docs/development/testing-workflow.md)** - RED-GREEN-REFACTOR cycle, test patterns by layer
- **[Testing Guide](docs/development/testing.md)** - Test infrastructure, fixtures, running tests
- **[Testing Patterns](docs/developer/patterns/AGENTS.md)** - Comprehensive testing patterns and examples

### Coverage Requirements

| Test Type        | Minimum Coverage | Enforcement   |
| ---------------- | ---------------- | ------------- |
| Backend Unit     | 85%              | CI gate       |
| Backend Combined | 95%              | CI gate       |
| Frontend         | 83%/77%/81%/84%  | CI gate       |
| E2E              | Critical paths   | Manual review |

### Quick Test Commands

```bash
# Backend unit tests (parallel)
uv run pytest backend/tests/unit/ -n auto --dist=worksteal

# Backend integration tests (serial)
uv run pytest backend/tests/integration/ -n0

# Frontend tests
cd frontend && npm test

# Full validation (recommended before PRs)
./scripts/validate.sh
```

## Git and Pre-commit Rules

**CRITICAL: Never bypass git pre-commit hooks.** For detailed git safety protocols and the "NEVER DISABLE TESTING" policy, see **[Git Workflow Guide](docs/development/git-workflow.md)**.

**Setup (run once per clone):**

```bash
pre-commit install                    # Install pre-commit hooks
pre-commit install --hook-type pre-push  # Install pre-push hooks
```

For pre-commit hook details, see **[Pre-commit Hooks](docs/development/hooks.md)**.

## Code Quality Tooling

For comprehensive code quality tool documentation, see **[Code Quality Tools](docs/development/code-quality.md)**.

### Quick Reference

```bash
# Full validation (recommended before PRs)
./scripts/validate.sh

# Dead code detection
uv run vulture backend/ --min-confidence 80
cd frontend && npx knip

# Architecture review
/code-review
```

## Key Design Decisions

- **Risk scoring:** LLM-determined (Nemotron analyzes detections and assigns 0-100 score)
- **Batch processing:** 90-second time windows with 30-second idle timeout
- **No auth:** Single-user local deployment
- **Retention:** 30 days
- **Deployment:** Fully containerized (Docker or Podman) with GPU passthrough for AI models

## AGENTS.md Navigation

Every directory contains an `AGENTS.md` file that documents purpose, key files, patterns, and entry points. **Always read the AGENTS.md file first when exploring a new directory.**

```bash
# List all AGENTS.md files
find . -name "AGENTS.md" -type f | head -20
```

### Key AGENTS.md Locations

| Directory                  | Purpose                           |
| -------------------------- | --------------------------------- |
| `/AGENTS.md`               | Project overview and entry points |
| `/ai/AGENTS.md`            | AI pipeline overview              |
| `/backend/AGENTS.md`       | Backend architecture overview     |
| `/backend/tests/AGENTS.md` | Test infrastructure overview      |
| `/frontend/AGENTS.md`      | Frontend architecture overview    |
| `/docs/AGENTS.md`          | Documentation overview            |

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
docs/decisions/        # Architectural decision records
```

## Session Workflow

1. Check available work in [Linear Active view](https://linear.app/nemotron-v3-home-security/team/NEM/active)
2. Filter by label (e.g., phase-1, backend, frontend)
3. Claim task by assigning to yourself and setting status to "In Progress"
4. Implement following TDD (test first for `tdd` labeled tasks)
5. Validate before closing: run `./scripts/validate.sh`
6. Close task by setting status to "Done" in Linear
7. End session: `git push`

## One-Task-One-PR Policy

Each Linear issue should result in exactly one PR:

- **PR title format:** `<type>: <issue title> (NEM-<id>)`
- **Example:** `fix: resolve WebSocket broadcast error (NEM-123)`

**Anti-patterns (do not do):**

| Bad PR Title                        | Problem                    |
| ----------------------------------- | -------------------------- |
| "fix: resolve 9 issues"             | Split into 9 PRs           |
| "fix: resolve 20 production issues" | Create 20 issues, 20 PRs   |
| "feat: X AND Y"                     | Split into separate issues |

**Why this matters:** Enables precise rollbacks, clear attribution, better code review quality, and easier regression identification.

## Issue Closure Requirements

Before marking an issue as "Done" in Linear, verify ALL of the following:

```bash
# Quick validation (recommended)
./scripts/validate.sh

# Or run individually:
uv run pytest backend/tests/unit/ -n auto --dist=worksteal  # Backend unit tests
uv run pytest backend/tests/integration/ -n0                 # Backend integration tests
cd frontend && npm test                                       # Frontend tests
uv run mypy backend/                                          # Backend type check
cd frontend && npm run typecheck                              # Frontend type check
pre-commit run --all-files                                    # Pre-commit hooks
```

### For UI Changes, Also Run

```bash
cd frontend && npx playwright test  # E2E tests (multi-browser)
```

**CRITICAL:** Do not close an issue if any validation fails. Fix the issue first.

## Development Documentation Index

| Document                                                     | Purpose                                             |
| ------------------------------------------------------------ | --------------------------------------------------- |
| [TDD Workflow](docs/development/testing-workflow.md)         | RED-GREEN-REFACTOR cycle, test patterns             |
| [Testing Guide](docs/development/testing.md)                 | Test infrastructure, fixtures, running tests        |
| [Git Workflow](docs/development/git-workflow.md)             | Git safety, pre-commit rules, NEVER DISABLE TESTING |
| [Pre-commit Hooks](docs/development/hooks.md)                | Detailed hook documentation                         |
| [Code Quality](docs/development/code-quality.md)             | Linting, formatting, static analysis                |
| [Linear Integration](docs/development/linear-integration.md) | MCP tools, workflow states, usage examples          |
| [Contributing](docs/development/contributing.md)             | PR process and code standards                       |
