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

CI workflows pin **uv version `0.9.18`** for reproducibility across all runners. This version is centrally defined in each workflow's `env` block:

```yaml
env:
  UV_VERSION: '0.9.18' # Centralized version for all workflow steps
```

**How to update uv version across all CI workflows:**

1. Identify the new uv version to use (check [astral-sh/setup-uv releases](https://github.com/astral-sh/setup-uv/releases))
2. Update the version in all `.github/workflows/*.yml` files:

```bash
# Replace old version with new version in all workflow files
find .github/workflows -name "*.yml" -exec sed -i "s/UV_VERSION: '0.9.18'/UV_VERSION: '0.10.0'/g" {} \;
```

3. Test locally with the new version:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh  # Install latest
uv self update --to 0.10.0                        # Install specific version
```

4. Commit and create a PR with the update

**Note:** Dependabot automatically monitors GitHub Actions versions (including `astral-sh/setup-uv`) and creates update PRs weekly. However, the hardcoded `UV_VERSION` must be manually updated.

## Issue Tracking

This project uses **Linear** for issue tracking:

- **Workspace:** [nemotron-v3-home-security](https://linear.app/nemotron-v3-home-security)
- **Team:** NEM
- **Team ID:** `998946a2-aa75-491b-a39d-189660131392`

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

Claude Code has access to Linear MCP tools for issue management. Available tools:

| Tool                         | Purpose                                  |
| ---------------------------- | ---------------------------------------- |
| `mcp__linear__list_issues`   | List issues with optional filters        |
| `mcp__linear__get_issue`     | Get detailed info about a specific issue |
| `mcp__linear__create_issue`  | Create a new issue                       |
| `mcp__linear__update_issue`  | Update an existing issue                 |
| `mcp__linear__search_issues` | Search issues by text query              |
| `mcp__linear__list_teams`    | List all teams in workspace              |
| `mcp__linear__list_projects` | List all projects                        |

### Workflow State UUIDs (NEM Team)

**IMPORTANT:** When updating issue status, you must use the workflow state UUID, not the status name.

| Status          | UUID                                   | Type      |
| --------------- | -------------------------------------- | --------- |
| **Backlog**     | `88b50a4e-75a1-4f34-a3b0-598bfd118aac` | backlog   |
| **Todo**        | `50ef9730-7d5e-43d6-b5e0-d7cac07af58f` | unstarted |
| **In Progress** | `b88c8ae2-2545-4c1b-b83a-bf2dde2c03e7` | started   |
| **In Review**   | `ec90a3c4-c160-44fc-aa7e-82bdca77aa46` | started   |
| **Done**        | `38267c1e-4458-4875-aa66-4b56381786e9` | completed |
| **Canceled**    | `232ef160-e291-4cc6-a3d9-7b4da584a2b2` | canceled  |
| **Duplicate**   | `3b4c9a4b-09ba-4b61-9dbb-fedbd31195ee` | canceled  |

### Linear MCP Usage Examples

```python
# List all Todo issues for NEM team
mcp__linear__list_issues(teamId="998946a2-aa75-491b-a39d-189660131392", status="Todo")

# Get details for a specific issue
mcp__linear__get_issue(issueId="NEM-123")

# Search for issues
mcp__linear__search_issues(query="prometheus metrics")

# Update issue status to "In Progress"
mcp__linear__update_issue(
    issueId="NEM-123",
    status="b88c8ae2-2545-4c1b-b83a-bf2dde2c03e7"  # In Progress UUID
)

# Close an issue (mark as Done)
mcp__linear__update_issue(
    issueId="NEM-123",
    status="38267c1e-4458-4875-aa66-4b56381786e9"  # Done UUID
)

# Update issue description
mcp__linear__update_issue(
    issueId="NEM-123",
    description="## Updated description\n\nNew content here..."
)

# Create a new issue
mcp__linear__create_issue(
    title="New feature request",
    teamId="998946a2-aa75-491b-a39d-189660131392",
    description="Description in markdown",
    priority=2  # 0=No priority, 1=Urgent, 2=High, 3=Medium, 4=Low
)
```

### Querying Workflow States

If you need to refresh or verify workflow state UUIDs, use the Linear GraphQL API:

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: $LINEAR_API_KEY" \
  -d '{"query": "{ workflowStates { nodes { id name type team { key } } } }"}'
```

## Task Execution Order

Tasks are organized into 8 execution phases. **Always complete earlier phases before starting later ones.**

### Phase 1: Project Setup (P0)

Foundation - directory structures, container setup, environment, dependencies.
[View in Linear](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-1)

### Phase 2: Database & Layout Foundation (P1)

PostgreSQL models, Redis connection, Tailwind theme, app layout.
[View in Linear](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-2)

### Phase 3: Core APIs & Components (P2)

Cameras API, system API, WebSocket hooks, API client, basic UI components.
[View in Linear](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-3)

### Phase 4: AI Pipeline (P3/P4)

File watcher, RT-DETRv2 wrapper, detector client, batch aggregator, Nemotron analyzer.
[View in Linear](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-4)

### Phase 5: Events & Real-time (P4)

Events API, detections API, WebSocket channels, GPU monitor, cleanup service.
[View in Linear](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-5)

### Phase 6: Dashboard Components (P3)

Risk gauge, camera grid, live activity feed, GPU stats, EventCard.
[View in Linear](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-6)

### Phase 7: Pages & Modals (P4)

Main dashboard, event timeline, event detail modal, settings pages.
[View in Linear](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-7)

### Phase 8: Integration & E2E (P4)

Unit tests, E2E tests, deployment verification, documentation.
[View in Linear](https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-8)

## Post-MVP Roadmap (After MVP is Operational)

After the MVP is **fully operational end-to-end** (Phases 1–8 complete, deployment verified, and tests passing),
review `docs/ROADMAP.md` to identify post-MVP enhancements and create new Linear issues accordingly.

## TDD Approach

This project follows **Test-Driven Development (TDD)** for all feature implementation. Tests are not an afterthought; they drive the design and ensure correctness from the start.

**For comprehensive testing patterns, fixtures, and examples, see [`docs/TESTING_GUIDE.md`](docs/TESTING_GUIDE.md).**

### The TDD Cycle: RED-GREEN-REFACTOR

1. **RED** - Write a failing test that defines the expected behavior
2. **GREEN** - Write the minimum code necessary to make the test pass
3. **REFACTOR** - Improve the code while keeping tests green

![TDD Cycle](docs/images/architecture/tdd-cycle.png)

### Pre-Implementation Checklist

Before writing any production code, complete this checklist:

- [ ] Understand the acceptance criteria from the Linear issue
- [ ] Identify the code layer(s) involved (API, service, component, E2E)
- [ ] Write test stubs for each acceptance criterion
- [ ] Run tests to confirm they fail (RED phase)
- [ ] Only then begin implementation

### Test Patterns by Layer

#### Backend API Routes (pytest + httpx)

```python
# backend/tests/unit/api/routes/test_cameras.py
import pytest
from httpx import AsyncClient
from backend.main import app

@pytest.mark.asyncio
async def test_get_camera_returns_camera_data(async_client: AsyncClient):
    """RED: Write this test first, then implement the endpoint."""
    response = await async_client.get("/api/cameras/front_door")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "front_door"
    assert "status" in data
    assert "last_seen" in data

@pytest.mark.asyncio
async def test_get_camera_not_found_returns_404(async_client: AsyncClient):
    """Test error handling for missing cameras."""
    response = await async_client.get("/api/cameras/nonexistent")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
```

#### Backend Services (pytest + mocking)

```python
# backend/tests/unit/services/test_detection_service.py
import pytest
from unittest.mock import AsyncMock, patch
from backend.services.detection import DetectionService

@pytest.mark.asyncio
async def test_process_image_calls_rtdetr_client():
    """RED: Test that service integrates with RT-DETR correctly."""
    mock_rtdetr = AsyncMock()
    mock_rtdetr.detect.return_value = [
        {"label": "person", "confidence": 0.95, "bbox": [100, 200, 300, 400]}
    ]

    service = DetectionService(rtdetr_client=mock_rtdetr)
    result = await service.process_image("/path/to/image.jpg")

    mock_rtdetr.detect.assert_called_once_with("/path/to/image.jpg")
    assert len(result.detections) == 1
    assert result.detections[0].label == "person"

@pytest.mark.asyncio
async def test_process_image_handles_rtdetr_timeout():
    """Test graceful handling of AI service timeouts."""
    mock_rtdetr = AsyncMock()
    mock_rtdetr.detect.side_effect = TimeoutError("RT-DETR timeout")

    service = DetectionService(rtdetr_client=mock_rtdetr)

    with pytest.raises(DetectionError) as exc_info:
        await service.process_image("/path/to/image.jpg")

    assert "timeout" in str(exc_info.value).lower()
```

#### Frontend Components (Vitest + React Testing Library)

```typescript
// frontend/src/components/RiskGauge.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { RiskGauge } from './RiskGauge';

describe('RiskGauge', () => {
  it('displays low risk styling for scores under 30', () => {
    // RED: Write test first, then implement component
    render(<RiskGauge score={25} />);

    const gauge = screen.getByRole('meter');
    expect(gauge).toHaveAttribute('aria-valuenow', '25');
    expect(gauge).toHaveClass('risk-low');
  });

  it('displays high risk styling for scores over 70', () => {
    render(<RiskGauge score={85} />);

    const gauge = screen.getByRole('meter');
    expect(gauge).toHaveClass('risk-high');
    expect(screen.getByText(/high risk/i)).toBeInTheDocument();
  });

  it('updates in real-time when score changes', async () => {
    const { rerender } = render(<RiskGauge score={20} />);
    expect(screen.getByRole('meter')).toHaveAttribute('aria-valuenow', '20');

    rerender(<RiskGauge score={80} />);
    expect(screen.getByRole('meter')).toHaveAttribute('aria-valuenow', '80');
  });
});
```

#### E2E Tests (Playwright)

```typescript
// frontend/tests/e2e/dashboard.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test('displays live camera feeds on load', async ({ page }) => {
    // RED: Write E2E test first to define user journey
    await page.goto('/');

    // Wait for WebSocket connection
    await expect(page.locator('[data-testid="ws-status"]')).toHaveText('Connected');

    // Verify camera grid loads
    const cameraCards = page.locator('[data-testid="camera-card"]');
    await expect(cameraCards).toHaveCount(4);

    // Verify each camera shows status
    for (const card of await cameraCards.all()) {
      await expect(card.locator('.camera-status')).toBeVisible();
    }
  });

  test('risk gauge updates when new detection arrives', async ({ page }) => {
    await page.goto('/');

    // Initial state
    const gauge = page.locator('[data-testid="risk-gauge"]');
    await expect(gauge).toHaveAttribute('aria-valuenow', '0');

    // Simulate detection via API (or mock WebSocket)
    await page.evaluate(() => {
      window.dispatchEvent(
        new CustomEvent('test:detection', {
          detail: { risk_score: 75 },
        })
      );
    });

    // Verify gauge updates
    await expect(gauge).toHaveAttribute('aria-valuenow', '75');
  });
});
```

### Using the TDD Skill

For complex features, invoke the TDD skill to guide your workflow:

```bash
/superpowers:test-driven-development
```

This skill will:

1. Help identify test cases from requirements
2. Generate test stubs for each layer
3. Guide you through the RED-GREEN-REFACTOR cycle
4. Ensure proper test coverage before completion

### Integration with Linear

Tasks labeled `tdd` are test-focused tasks that pair with feature tasks:
[View TDD issues](https://linear.app/nemotron-v3-home-security/team/NEM/label/tdd)

**Workflow for TDD-labeled issues:**

1. **Claim both tasks** - The feature task and its corresponding TDD task
2. **Start with tests** - Implement tests from the TDD issue first
3. **Verify RED** - Run tests to confirm they fail appropriately
4. **Implement feature** - Write code to make tests pass (GREEN)
5. **Refactor** - Clean up while keeping tests green
6. **Close TDD issue first** - Then close the feature issue

### Test Coverage Requirements

This project enforces strict coverage thresholds:

| Test Type        | Minimum Coverage | Enforcement   |
| ---------------- | ---------------- | ------------- |
| Backend Unit     | 85%              | CI gate       |
| Backend Combined | 95%              | CI gate       |
| Frontend         | 83%/77%/81%/84%  | CI gate       |
| E2E              | Critical paths   | Manual review |

**Note:** Frontend thresholds are statements/branches/functions/lines respectively.
See `pyproject.toml` (backend) and `vite.config.ts` (frontend) for authoritative values.

**Coverage Commands:**

```bash
# Backend coverage report
uv run pytest backend/tests/unit/ --cov=backend --cov-report=term-missing

# Frontend coverage report
cd frontend && npm test -- --coverage

# Full coverage report
./scripts/validate.sh --coverage
```

### Never Disable Testing

See the **[NEVER DISABLE TESTING](#never-disable-testing)** section below. This is an absolute rule:

- Do NOT skip tests to pass CI
- Do NOT lower coverage thresholds
- Do NOT comment out failing tests
- FIX the code or FIX the test

### PR Checklist for TDD Verification

Before creating a PR, verify:

- [ ] All new code has corresponding tests
- [ ] Tests were written BEFORE implementation (TDD)
- [ ] Tests cover happy path AND error cases
- [ ] Coverage thresholds are met (85% backend unit, 95% backend combined)
- [ ] No tests were skipped or disabled
- [ ] E2E tests pass for UI changes

### Testing Resources

- **Test Infrastructure:** See `backend/tests/AGENTS.md`
- **Fixtures and Factories:** See `backend/tests/conftest.py`
- **E2E Test Patterns:** See `frontend/tests/e2e/README.md`
- **Coverage Reports:** Generated in `coverage/` directory after test runs

## Testing Requirements

**All features must have tests written at time of development.** No feature is complete without:

1. **Unit tests** - Test individual functions/components in isolation
2. **Integration tests** - Test interactions between components
3. **Property-based tests** - Use Hypothesis for model invariants

### Test Locations

```
backend/tests/
  unit/              # Python unit tests (pytest) - 8,229 tests
  integration/       # API and service integration tests - 1,556 tests (4 domain shards)
frontend/
  src/**/*.test.ts   # Component and hook tests (Vitest) - 135 test files (8 shards)
  tests/e2e/         # Playwright E2E tests - 26 spec files (4 Chromium shards)
```

### Test Parallelization Strategy

The CI pipeline uses aggressive parallelization to reduce test execution time by ~60-70%:

| Test Suite                    | Parallelization               | CI Jobs             |
| ----------------------------- | ----------------------------- | ------------------- |
| Backend Unit                  | `pytest-xdist` with worksteal | 1 job, auto workers |
| Backend Integration           | Domain-based sharding         | 4 parallel jobs     |
| Frontend Vitest               | Matrix sharding               | 8 parallel shards   |
| Frontend E2E (Chromium)       | Playwright sharding           | 4 parallel shards   |
| Frontend E2E (Firefox/WebKit) | Non-blocking                  | 1 job each          |

**Integration Test Shards:**

- API routes (`integration-tests-api`)
- WebSocket/PubSub (`integration-tests-websocket`)
- Services/Business logic (`integration-tests-services`)
- Database models (`integration-tests-models`)

For full performance metrics and baselines, see [`docs/TEST_PERFORMANCE_METRICS.md`](docs/TEST_PERFORMANCE_METRICS.md).

### Validation Workflow

After implementing any feature, **dispatch a validation agent** to run tests:

```bash
# Backend unit tests (parallel ~10s)
uv run pytest backend/tests/unit/ -n auto --dist=worksteal

# Backend integration tests (serial ~70s)
uv run pytest backend/tests/integration/ -n0

# Frontend tests
cd frontend && npm test

# E2E tests (multi-browser)
cd frontend && npx playwright test
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

**Branch Protection (GitHub enforced):**

- All CI jobs must pass before merge
- Admin bypass is disabled
- CODEOWNERS review required

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
uv run pytest backend/tests/ -v

# Frontend
cd frontend && npm test

# Full validation (recommended before PRs)
./scripts/validate.sh

# Pre-commit (runs lint/format checks)
pre-commit run --all-files
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

### AGENTS.md Locations (98 files)

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

Before marking an issue as "Done" in Linear, verify ALL of the following:

### Required Checklist

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

### Closure Workflow

1. Ensure all code is committed and pushed
2. Run validation: `./scripts/validate.sh`
3. If all tests pass, mark the issue as "Done" in Linear
4. If tests fail, fix the issue and re-run before closing

**CRITICAL:** Do not close an issue if any validation fails. Fix the issue first.
