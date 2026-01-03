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

## Issue Tracking

This project uses **Linear** for issue tracking:

- **Workspace:** [nemotron-v3-home-security](https://linear.app/nemotron-v3-home-security)
- **Team:** NEM

```bash
# View active issues
# https://linear.app/nemotron-v3-home-security/team/NEM/active

# Filter by label (e.g., phase-1)
# https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-1
```

Issues are organized with:

- **Priorities:** Urgent, High, Medium, Low (mapped from P0-P4)
- **Labels:** phase-1 through phase-8, backend, frontend, tdd, etc.
- **Parent/sub-issues:** Epics contain sub-tasks

### Linear MCP Tools

When using Claude Code, query Linear directly via MCP tools:

```python
# List open issues (must filter by status to find open work)
mcp__linear__list_issues(teamId="998946a2-aa75-491b-a39d-189660131392", status="Todo", first=100)
mcp__linear__list_issues(teamId="998946a2-aa75-491b-a39d-189660131392", status="In Progress", first=100)

# Search issues by text
mcp__linear__search_issues(query="WebSocket")

# Get full issue details
mcp__linear__get_issue(issueId="ISSUE-ID")

# Update issue status
mcp__linear__update_issue(issueId="ISSUE-ID", status="In Progress")
```

**Important:** The default `list_issues` returns only 50 results sorted by recent activity, which may miss open issues. Always:

- Filter by `status` ("Todo", "In Progress") to find open work
- Set `first=100` to get more results
- **Team ID:** `998946a2-aa75-491b-a39d-189660131392`

## Testing

This project follows **Test-Driven Development (TDD)**: write tests first, then implement.

### TDD Cycle

1. **RED** - Write a failing test
2. **GREEN** - Write minimum code to pass
3. **REFACTOR** - Improve while keeping tests green

For complex features, use `/test-driven-development` to guide your workflow.

### Test Locations

```
backend/tests/
  unit/              # Python unit tests (pytest)
  integration/       # API and service integration tests
frontend/
  src/**/*.test.ts   # Component and hook tests (Vitest)
  tests/e2e/         # Playwright E2E tests (multi-browser)
```

For test patterns and examples, see actual test files and `backend/tests/AGENTS.md`.

### Coverage Requirements

| Test Type   | Minimum | Enforcement |
| ----------- | ------- | ----------- |
| Unit        | 92%     | CI gate     |
| Integration | 50%     | CI gate     |
| Combined    | 90%     | CI gate     |

### Running Tests

```bash
# Full validation (recommended)
./scripts/validate.sh

# Individual test suites
uv run pytest backend/tests/unit/ -n auto --dist=worksteal   # Backend unit (parallel)
uv run pytest backend/tests/integration/ -n0                  # Backend integration (serial)
cd frontend && npm test                                       # Frontend unit
cd frontend && npx playwright test                            # E2E (multi-browser)
```

**CRITICAL:** Do not mark a task complete until all tests pass.

## Git and Pre-commit Rules

**CRITICAL: Never bypass git pre-commit hooks.** All commits must pass pre-commit checks including:

- `ruff check` - Python linting
- `ruff format` - Python formatting
- `mypy` - Python type checking
- `eslint` - TypeScript/JavaScript linting
- `prettier` - Code formatting

**Test Strategy (optimized for performance):**

- **Pre-commit:** Fast lint/format/type checks only (~10-30 seconds)
- **Pre-push:** Unit tests run on push (install with: `pre-commit install --hook-type pre-push`)
- **CI:** Full test suite with 95% coverage enforcement
- **Manual:** Run `./scripts/validate.sh` before PRs for full validation

**Do NOT use:**

- `git commit --no-verify`
- `git push --no-verify`
- Any flags that skip pre-commit hooks

**Branch Protection (GitHub enforced):**

- All CI jobs must pass before merge
- Admin bypass is disabled
- CODEOWNERS review required

## NEVER DISABLE TESTING

> **⛔ ABSOLUTE RULE: Tests must NEVER be disabled, removed, or bypassed.**

Previous agents have violated this by lowering coverage thresholds, skipping tests, or using `--no-verify`.

**If tests fail, FIX THE CODE or FIX THE TEST. Do not:**

- Disable or skip tests
- Lower coverage thresholds
- Use `--no-verify` flags
- Remove test files or assertions

**Setup (run once per clone):**

```bash
pre-commit install                       # Install pre-commit hooks
pre-commit install --hook-type pre-push  # Install pre-push hooks
```

## Code Quality Tooling

This project uses additional code quality tools beyond linting:

### Pre-commit Hooks (Local)

| Hook     | Purpose                                                 | Runtime |
| -------- | ------------------------------------------------------- | ------- |
| Hadolint | Docker best practices, CIS benchmarks                   | ~1-2s   |
| Semgrep  | Security scanning (SQL injection, path traversal, etc.) | ~2-5s   |

These run automatically on commit. Skip with `SKIP=hadolint,semgrep git commit` in emergencies (CI still catches issues).

### CI-Only Checks

| Tool         | Purpose                 | What It Catches                           |
| ------------ | ----------------------- | ----------------------------------------- |
| Vulture      | Python dead code        | Unused functions, imports, variables      |
| Knip         | TypeScript dead code    | Unused exports, dependencies, files       |
| Radon        | Complexity metrics      | Functions with cyclomatic complexity > 10 |
| API Coverage | Backend→Frontend parity | Endpoints with no frontend consumers      |

### Running Locally

```bash
# Dead code detection
uv run vulture backend/ --min-confidence 80
cd frontend && npx knip

# Complexity analysis
uv run radon cc backend/ -a -s  # Cyclomatic complexity
uv run radon mi backend/ -s     # Maintainability index

# API coverage
./scripts/check-api-coverage.sh
```

### Architecture Review

Use the existing superpowers code reviewer for architecture concerns:

```
/code-review
```

This checks: scope creep, over-engineering, pattern violations, SOLID principles, and architectural drift.

## Key Design Decisions

- **Risk scoring:** LLM-determined (Nemotron analyzes detections and assigns 0-100 score)
- **Batch processing:** 90-second time windows with 30-second idle timeout
- **No auth:** Single-user local deployment
- **Retention:** 30 days
- **Deployment:** Fully containerized (Docker or Podman) with GPU passthrough for AI models

## AGENTS.md Navigation

Every directory contains an `AGENTS.md` file that documents:

- Purpose of the directory
- Key files and what they do
- Important patterns and conventions
- Entry points for understanding the code

**Always read the AGENTS.md file first when exploring a new directory.**

```bash
# List all AGENTS.md files
find . -name "AGENTS.md" -type f | head -20
```

### AGENTS.md Locations (34 files)

| Directory                            | Purpose                           |
| ------------------------------------ | --------------------------------- |
| `/AGENTS.md`                         | Project overview and entry points |
| `/ai/AGENTS.md`                      | AI pipeline overview              |
| `/ai/rtdetr/AGENTS.md`               | RT-DETRv2 object detection server |
| `/ai/nemotron/AGENTS.md`             | Nemotron LLM risk analysis        |
| `/backend/AGENTS.md`                 | Backend architecture overview     |
| `/backend/api/AGENTS.md`             | API layer structure               |
| `/backend/api/routes/AGENTS.md`      | REST endpoint documentation       |
| `/backend/api/schemas/AGENTS.md`     | Pydantic schema definitions       |
| `/backend/core/AGENTS.md`            | Config, database, Redis clients   |
| `/backend/models/AGENTS.md`          | SQLAlchemy ORM models             |
| `/backend/services/AGENTS.md`        | AI pipeline services              |
| `/backend/tests/AGENTS.md`           | Test infrastructure overview      |
| `/frontend/AGENTS.md`                | Frontend architecture overview    |
| `/frontend/src/AGENTS.md`            | Source code organization          |
| `/frontend/src/components/AGENTS.md` | Component hierarchy               |
| `/frontend/src/hooks/AGENTS.md`      | Custom React hooks                |
| `/docs/AGENTS.md`                    | Documentation overview            |

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

**Exceptions:**

- Trivial related typo fixes can be batched
- Changes to the same function/component in same file

**Why this matters:**

- Enables precise rollbacks without reverting unrelated changes
- Clear attribution of which change fixed which issue
- Better code review quality (smaller, focused diffs)
- Regressions are easier to identify and bisect

## Issue Closure Requirements

Before marking an issue as "Done" in Linear:

1. Ensure all code is committed and pushed
2. Run `./scripts/validate.sh` (for UI changes, also run `npx playwright test`)
3. If all tests pass, mark the issue as "Done"
4. If tests fail, fix the issue first
