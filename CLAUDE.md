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

Foundation - directory structures, container setup, environment, dependencies.

```bash
bd list --label phase-1
```

### Phase 2: Database & Layout Foundation (P1) - 6 tasks

PostgreSQL models, Redis connection, Tailwind theme, app layout.

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

## Post-MVP Roadmap (After MVP is Operational)

After the MVP is **fully operational end-to-end** (Phases 1–8 complete, deployment verified, and tests passing),
review `docs/ROADMAP.md` to identify post-MVP enhancements and create/claim new beads tasks accordingly.

## TDD Approach

Tasks labeled `tdd` are test tasks that should be completed alongside their feature tasks:

```bash
bd list --label tdd
```

## Testing Requirements

**All features must have tests written at time of development.** No feature is complete without:

1. **Unit tests** - Test individual functions/components in isolation
2. **Integration tests** - Test interactions between components

### Test Locations

```
backend/tests/
  unit/              # Python unit tests (pytest)
  integration/       # API and service integration tests
frontend/
  src/**/*.test.ts   # Component and hook tests (Vitest)
  tests/e2e/         # End-to-end tests
```

### Validation Workflow

After implementing any feature, **dispatch a validation agent** to run tests:

```bash
# Backend tests
pytest backend/tests/ -v

# Frontend tests
cd frontend && npm test

# Full validation
pytest backend/tests/ -v && cd frontend && npm test
```

**CRITICAL:** Do not mark a task as complete until:

- All relevant tests pass
- A validation agent has confirmed no regressions
- Test coverage includes both happy path and error cases

### When to Dispatch Validation Agents

- After implementing any new feature
- After modifying existing code
- Before closing any task
- Before committing code

Validation agents should run the full test suite and report any failures. Fix all failures before proceeding.

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

## NEVER DISABLE TESTING

> **⛔ ABSOLUTE RULE: Unit and integration tests must NEVER be disabled, removed, or bypassed.**

This rule is non-negotiable. Previous agents have violated this rule by:

- Moving test hooks from `pre-commit` to `pre-push` stage (reducing test frequency)
- Lowering coverage thresholds to pass CI
- Commenting out or skipping failing tests
- Removing test assertions to make tests pass

**If tests are failing, FIX THE CODE or FIX THE TESTS. Do not:**

1. Disable the test hook
2. Change the hook stage to run less frequently
3. Lower coverage thresholds
4. Skip tests with `@pytest.skip` without a documented reason
5. Remove test files or test functions
6. Use `--no-verify` flags

**Required hooks that must remain active:**

| Hook                      | Stage    | Purpose                            |
| ------------------------- | -------- | ---------------------------------- |
| `fast-test`               | pre-push | Runs unit tests before every push  |
| Backend Unit Tests        | CI       | Full unit test suite with coverage |
| Backend Integration Tests | CI       | API and service integration tests  |
| Frontend Tests            | CI       | Component and hook tests           |
| E2E Tests                 | CI       | End-to-end browser tests           |

**Setup (run once per clone):**

```bash
pre-commit install                    # Install pre-commit hooks
pre-commit install --hook-type pre-push  # Install pre-push hooks
```

If you encounter test failures, your job is to investigate and fix them, not to disable the safety net.

If pre-commit checks fail, fix the issues before committing. Run the full test suite after all agents complete work:

```bash
# Backend
source .venv/bin/activate && python -m pytest backend/tests/ -v

# Frontend
cd frontend && npm test

# Full validation (recommended before PRs)
./scripts/validate.sh

# Pre-commit (runs lint/format checks)
pre-commit run --all-files
```

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

1. Check available work: `bd ready`
2. Filter by current phase: `bd list --label phase-N`
3. Claim task: `bd update <id> --status in_progress`
4. Implement following TDD (test first for `tdd` labeled tasks)
5. Close task: `bd close <id>`
6. End session: `bd sync && git push`
