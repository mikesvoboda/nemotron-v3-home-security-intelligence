# Claude Code Instructions

This project is an AI-powered home security monitoring dashboard. See `AGENTS.md` for detailed file structure, entry points, and codebase navigation.

## Quick Reference

| Resource                    | Location                                                                                                                 |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| File structure & navigation | `AGENTS.md`                                                                                                              |
| Issue tracking              | [Linear](https://linear.app/nemotron-v3-home-security/team/NEM/active) (Team ID: `998946a2-aa75-491b-a39d-189660131392`) |
| Linear MCP tools            | [docs/development/linear-integration.md](docs/development/linear-integration.md)                                         |
| Post-MVP roadmap            | `docs/ROADMAP.md` (pursue **after Phases 1-8 are operational**)                                                          |

## Setup

```bash
./setup.sh              # First-time setup (creates .env, installs deps)
uv sync --extra dev     # Sync Python dependencies
cd frontend && bun install  # Sync frontend dependencies
pre-commit install      # Install git hooks
```

## Container Rebuild Rules

**CRITICAL: Always rebuild containers without cache and from the local worktree.**

When rebuilding containers during development:

1. **Always use `--no-cache`** to ensure changes are picked up (cached layers may contain stale code)
2. **Always rebuild from your local worktree/branch**, not from `main` directly
3. **Never use pre-built GHCR images** when testing local changes

```bash
# Correct: Rebuild without cache from local code
podman-compose -f docker-compose.prod.yml build --no-cache frontend
podman-compose -f docker-compose.prod.yml build --no-cache backend

# Correct: Rebuild and restart
podman-compose -f docker-compose.prod.yml up -d --build --force-recreate frontend

# Wrong: Simple restart won't pick up code changes
podman-compose -f docker-compose.prod.yml restart frontend  # DON'T DO THIS

# Wrong: Rebuild with cache may use stale layers
podman-compose -f docker-compose.prod.yml build frontend  # DON'T DO THIS
```

**Why this matters:** Docker/Podman layer caching can cause confusing bugs where your code changes aren't reflected in the running container. Always use `--no-cache` when rebuilding during development.

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
ln -sf ../../scripts/hooks/post-checkout .git/hooks/post-checkout  # Worktree protection
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
  yolo26/              # YOLO26 detection server
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

## Linear Task Management

**CRITICAL:** The Linear MCP tools require workflow state UUIDs, not status names like "Done".

### Workflow State UUIDs (NEM Team)

| Status          | UUID                                   |
| --------------- | -------------------------------------- |
| **Backlog**     | `88b50a4e-75a1-4f34-a3b0-598bfd118aac` |
| **Todo**        | `50ef9730-7d5e-43d6-b5e0-d7cac07af58f` |
| **In Progress** | `b88c8ae2-2545-4c1b-b83a-bf2dde2c03e7` |
| **In Review**   | `ec90a3c4-c160-44fc-aa7e-82bdca77aa46` |
| **Done**        | `38267c1e-4458-4875-aa66-4b56381786e9` |
| **Canceled**    | `232ef160-e291-4cc6-a3d9-7b4da584a2b2` |

### Updating Task Status

```python
# WRONG - will fail with "stateId must be a UUID"
mcp__linear__update_issue(issueId="<uuid>", status="Done")

# CORRECT - use the workflow state UUID
mcp__linear__update_issue(
    issueId="<issue-uuid>",
    status="38267c1e-4458-4875-aa66-4b56381786e9"  # Done UUID
)
```

### Creating Epics with Subtasks

1. **Create the epic first:**

```python
epic = mcp__linear__create_issue(
    title="Epic: Feature Name",
    teamId="998946a2-aa75-491b-a39d-189660131392",
    description="## Overview\n\nEpic description...",
    priority=2
)
# Note the epic's issue ID from the response
```

2. **Create subtasks and link to epic:**

```python
# The Linear MCP doesn't support parentId directly
# Create subtasks mentioning the epic in description
mcp__linear__create_issue(
    title="Phase 1.1: Subtask Name",
    teamId="998946a2-aa75-491b-a39d-189660131392",
    description="Parent: NEM-XXX (Epic)\n\n## Task\n\nDescription..."
)
```

**Note:** To properly link subtasks to epics, use the Linear UI or GraphQL API. The MCP tool creates standalone issues.

### Batch Closing Tasks

When completing an epic with multiple subtasks, close all tasks efficiently:

```python
# Get the Done UUID
DONE_UUID = "38267c1e-4458-4875-aa66-4b56381786e9"

# Close multiple tasks (can be parallelized)
mcp__linear__update_issue(issueId="<task-1-uuid>", status=DONE_UUID)
mcp__linear__update_issue(issueId="<task-2-uuid>", status=DONE_UUID)
# ... close all subtasks
mcp__linear__update_issue(issueId="<epic-uuid>", status=DONE_UUID)  # Close epic last
```

### Finding Task UUIDs

```python
# Search for tasks by keyword
results = mcp__linear__search_issues(query="feature name", first=50)
# Each result includes 'id' (the UUID) and 'url'

# Get specific issue details
issue = mcp__linear__get_issue(issueId="NEM-123")
```

### Common Patterns

| Action           | Tool Call                                                    |
| ---------------- | ------------------------------------------------------------ |
| Start work       | `update_issue(issueId, status="b88c8ae2-...")` (In Progress) |
| Request review   | `update_issue(issueId, status="ec90a3c4-...")` (In Review)   |
| Complete task    | `update_issue(issueId, status="38267c1e-...")` (Done)        |
| Search issues    | `search_issues(query="keyword")`                             |
| List team issues | `list_issues(teamId="998946a2-...")`                         |

For complete documentation, see **[Linear Integration Guide](docs/development/linear-integration.md)**.

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

## Multi-GPU Configuration

The system supports multi-GPU configurations for distributing AI workloads. For the complete user guide, see **[Multi-GPU Support](docs/development/multi-gpu.md)**.

### Key Files

| Component        | Location                                             |
| ---------------- | ---------------------------------------------------- |
| API Schemas      | `backend/api/schemas/gpu_config.py`                  |
| Database Models  | `backend/models/gpu_config.py`                       |
| Config Service   | `backend/services/gpu_config_service.py`             |
| Frontend Hook    | `frontend/src/hooks/useGpuConfig.ts`                 |
| API Client       | `frontend/src/services/gpuConfigApi.ts`              |
| Override File    | `config/docker-compose.gpu-override.yml` (generated) |
| Assignments File | `config/gpu-assignments.yml` (generated)             |
| Design Document  | `docs/plans/2025-01-23-multi-gpu-support-design.md`  |

### Testing GPU Features Locally

```bash
# Run GPU-related tests
uv run pytest backend/tests/unit/services/test_gpu_config_service.py -v
uv run pytest backend/tests/unit/api/schemas/test_gpu_config.py -v
uv run pytest backend/tests/unit/models/test_gpu_config.py -v

# Frontend tests
cd frontend && npm test -- --testPathPattern=useGpuConfig
cd frontend && npm test -- --testPathPattern=gpuConfigApi
```

### API Endpoints

| Method | Endpoint                         | Purpose                                |
| ------ | -------------------------------- | -------------------------------------- |
| GET    | `/api/system/gpus`               | List detected GPUs with utilization    |
| GET    | `/api/system/gpu-config`         | Get current assignments and strategies |
| PUT    | `/api/system/gpu-config`         | Update assignments                     |
| POST   | `/api/system/gpu-config/apply`   | Apply config and restart services      |
| GET    | `/api/system/gpu-config/status`  | Get restart progress and health        |
| POST   | `/api/system/gpu-config/detect`  | Re-scan for GPUs                       |
| GET    | `/api/system/gpu-config/preview` | Preview auto-assignment for strategy   |

## Video Analytics Services

Key services for video analytics features:

| Service               | Location                                        | Purpose                                       |
| --------------------- | ----------------------------------------------- | --------------------------------------------- |
| **Zone Service**      | `backend/services/zone_service.py`              | Zone detection, line crossing, dwell tracking |
| **Face Detector**     | `backend/services/face_detector.py`             | Face detection using YOLO11                   |
| **Plate Detector**    | `backend/services/plate_detector.py`            | License plate detection and OCR               |
| **Re-ID Service**     | `backend/services/reid_service.py`              | Person re-identification across cameras       |
| **Entity Clustering** | `backend/services/entity_clustering_service.py` | Embedding similarity matching                 |
| **Household Matcher** | `backend/services/household_matcher.py`         | Match detections to household members         |
| **Context Enricher**  | `backend/services/context_enricher.py`          | Aggregate context from zones, baselines       |
| **Baseline Service**  | `backend/services/baseline.py`                  | Activity baseline tracking                    |
| **Model Zoo**         | `backend/services/model_zoo.py`                 | On-demand AI model management                 |

### Video Analytics Documentation

| Document                                                      | Purpose                                                      |
| ------------------------------------------------------------- | ------------------------------------------------------------ |
| [Video Analytics Guide](docs/guides/video-analytics.md)       | AI pipeline overview, detection, scene understanding         |
| [Zone Configuration Guide](docs/guides/zone-configuration.md) | Zone setup, dwell time, line crossing, household integration |
| [Face Recognition Guide](docs/guides/face-recognition.md)     | Face detection, person re-ID, household matching             |
| [Analytics API](docs/api/analytics-endpoints.md)              | Analytics endpoints reference                                |

### Analytics API Endpoints

| Method | Endpoint                                 | Purpose                           |
| ------ | ---------------------------------------- | --------------------------------- |
| GET    | `/api/analytics/detection-trends`        | Daily detection counts            |
| GET    | `/api/analytics/risk-history`            | Risk level distribution over time |
| GET    | `/api/analytics/camera-uptime`           | Camera uptime percentages         |
| GET    | `/api/analytics/object-distribution`     | Detection counts by object type   |
| GET    | `/api/analytics/risk-score-distribution` | Risk score histogram              |
| GET    | `/api/analytics/risk-score-trends`       | Average risk score over time      |

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
| [Multi-GPU Support](docs/development/multi-gpu.md)           | GPU configuration and assignment strategies         |
| [Video Analytics](docs/guides/video-analytics.md)            | AI detection pipeline and features                  |
| [Zone Configuration](docs/guides/zone-configuration.md)      | Detection zone setup and intelligence               |
| [Face Recognition](docs/guides/face-recognition.md)          | Face detection and person re-identification         |
