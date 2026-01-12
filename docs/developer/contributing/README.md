# Contributing Guide

> Complete guide for contributing to Home Security Intelligence: workflow, code quality, and best practices.

---

## Quick Start

```bash
# 1. Set up development environment
./setup.sh                    # Generate .env and docker-compose.override.yml
uv sync --extra dev           # Install Python dependencies
cd frontend && npm install    # Install frontend dependencies

# 2. Install pre-commit hooks
pre-commit install
pre-commit install --hook-type pre-push

# 3. Start services
podman-compose -f docker-compose.prod.yml up -d postgres redis

# 4. Run validation
./scripts/validate.sh
```

---

## Development Workflow

### 1. Find and Claim Work

This project uses **Linear** for issue tracking:

- **Workspace:** [nemotron-v3-home-security](https://linear.app/nemotron-v3-home-security)
- **Team:** NEM
- **Active Issues:** [View Active](https://linear.app/nemotron-v3-home-security/team/NEM/active)

Filter by phase labels (phase-1 through phase-8) to find work appropriate for current project stage.

### 2. Create a Branch

```bash
git checkout -b feature/camera-grid-pagination  # Features
git checkout -b fix/websocket-reconnect         # Bug fixes
git checkout -b refactor/batch-aggregator       # Refactoring
```

### 3. Implement with TDD

For tasks labeled `tdd`:

1. Write tests first (RED)
2. Implement the feature (GREEN)
3. Refactor while keeping tests passing

### 4. Commit Changes

Use conventional commit format:

```bash
git commit -m "feat(cameras): add pagination to camera list endpoint"
git commit -m "fix(websocket): handle reconnection on network failure"
git commit -m "test(events): add integration tests for event filtering"
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`

### 5. Create Pull Request

```bash
./scripts/validate.sh           # Run before PR
git push -u origin feature/my-feature
gh pr create --title "feat: my feature (NEM-123)"
```

**One Task Per PR:** Each PR should address exactly ONE Linear issue.

---

## Code Quality

### Pre-commit Hooks

All commits must pass pre-commit hooks. **Never bypass them.**

| Hook        | Stage      | Purpose                |
| ----------- | ---------- | ---------------------- |
| ruff        | pre-commit | Python linting         |
| ruff-format | pre-commit | Python formatting      |
| mypy        | pre-commit | Python type checking   |
| eslint      | pre-commit | TypeScript linting     |
| prettier    | pre-commit | Code formatting        |
| hadolint    | pre-commit | Dockerfile linting     |
| semgrep     | pre-commit | Security scanning      |
| fast-test   | pre-push   | Unit tests before push |

**Forbidden Commands:**

- `git commit --no-verify`
- `git push --no-verify`
- `SKIP=hook-name git commit` (except emergencies)

### Running Quality Checks

```bash
# Full validation (recommended before PRs)
./scripts/validate.sh

# Backend checks
uv run ruff check --fix backend/   # Lint and fix
uv run ruff format backend/        # Format
uv run mypy backend/               # Type check

# Frontend checks
cd frontend
npm run lint:fix                   # Lint and fix
npm run format                     # Format
npm run typecheck                  # Type check

# Run all pre-commit hooks
pre-commit run --all-files
```

### Coverage Requirements

| Test Type        | Threshold    | Enforcement |
| ---------------- | ------------ | ----------- |
| Backend Unit     | 85%          | CI gate     |
| Backend Combined | 95%          | CI gate     |
| Frontend         | 83/77/81/84% | CI gate     |

---

## Python Dependencies (uv)

This project uses **uv** for Python dependency management:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies
uv sync --extra dev              # Install all dev dependencies
uv sync --group lint             # Install only lint tools
uv sync --group test             # Install only test tools

# Add dependencies
uv add httpx                     # Production dependency
uv add --dev pytest-sugar        # Dev dependency

# Run commands
uv run pytest backend/tests/     # Run tests
uv run ruff check backend/       # Run linter

# Update lock file
uv lock                          # After editing pyproject.toml
```

**Key Files:**

- `pyproject.toml` - Dependencies and tool configuration
- `uv.lock` - Locked dependency versions (commit this)
- `.python-version` - Python version (3.14)

**CI pins uv version `0.9.18`** for reproducibility.

---

## Testing

### Test Commands

```bash
# Backend unit tests (parallel)
uv run pytest backend/tests/unit/ -n auto --dist=worksteal

# Backend integration tests (serial)
uv run pytest backend/tests/integration/ -n0

# Frontend unit tests
cd frontend && npm test

# Frontend E2E tests
cd frontend && npx playwright test

# With coverage
uv run pytest backend/tests/ --cov=backend --cov-report=html
```

### TDD Workflow

1. Write a failing test (RED)
2. Write minimum code to pass (GREEN)
3. Refactor while keeping tests green

For complex features, use `/superpowers:test-driven-development`.

---

## Git Safety

### NEVER DISABLE TESTING

This rule is non-negotiable:

- Do NOT disable test hooks
- Do NOT lower coverage thresholds
- Do NOT skip tests without documented reason
- Do NOT use `--no-verify` flags

**If tests fail, fix the code or fix the tests.**

### Required Hooks

| Hook                      | Stage    | Purpose                |
| ------------------------- | -------- | ---------------------- |
| fast-test                 | pre-push | Unit tests before push |
| Backend Unit Tests        | CI       | Full test suite        |
| Backend Integration Tests | CI       | API and service tests  |
| Frontend Tests            | CI       | Component tests        |
| E2E Tests                 | CI       | Browser tests          |

---

## Issue Closure Checklist

Before marking a Linear issue as "Done":

```bash
# Quick validation
./scripts/validate.sh

# Or run individually:
uv run pytest backend/tests/unit/ -n auto          # Unit tests
uv run pytest backend/tests/integration/ -n0       # Integration tests
cd frontend && npm test                            # Frontend tests
uv run mypy backend/                               # Type check
cd frontend && npm run typecheck                   # Frontend types
pre-commit run --all-files                         # All hooks
```

For UI changes, also run:

```bash
cd frontend && npx playwright test                 # E2E tests
```

**Do not close an issue if any validation fails.**

---

## File Organization

### Backend

```
backend/
  api/routes/       # FastAPI endpoints
  api/schemas/      # Pydantic schemas
  core/             # Infrastructure (config, database, redis)
  models/           # SQLAlchemy models
  services/         # Business logic
  tests/
    unit/           # Unit tests
    integration/    # Integration tests
```

### Frontend

```
frontend/
  src/
    components/     # React components
    hooks/          # Custom hooks
    services/       # API client
    types/          # TypeScript types
  tests/
    e2e/            # Playwright tests
```

---

## Security Guidelines

### Never Commit

- `.env` files with real credentials
- API keys or tokens
- Private keys or certificates
- Database connection strings with passwords

### Code Security

- Validate all user input
- Use parameterized queries (SQLAlchemy handles this)
- Sanitize file paths (prevent traversal)
- Log security-relevant events

---

## Related Documentation

| Document                                          | Purpose                    |
| ------------------------------------------------- | -------------------------- |
| [Testing Guide](../../TESTING_GUIDE.md)           | Test patterns and fixtures |
| [Code Quality](../../development/code-quality.md) | Tool configuration         |
| [Pre-commit Hooks](../../development/hooks.md)    | Hook documentation         |
| [CLAUDE.md](../../../CLAUDE.md)                   | Project instructions       |

---

[Back to Developer Hub](../README.md) | [Back to Documentation Index](../../README.md)
