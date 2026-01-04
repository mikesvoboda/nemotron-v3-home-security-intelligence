---
title: Code Quality Tools
source_refs:
  - pyproject.toml:84
  - .pre-commit-config.yaml:1
  - frontend/eslint.config.mjs:1
  - frontend/package.json:1
  - frontend/tsconfig.json:1
  - .github/workflows/ci.yml:1
---

# Code Quality Tools

This document describes all code quality tools used in the project, their configuration, and how to run them locally.

## Overview

The project uses a comprehensive suite of tools to maintain code quality:

| Layer    | Tool       | Purpose                | Config File                     |
| -------- | ---------- | ---------------------- | ------------------------------- |
| Backend  | Ruff       | Linting + Formatting   | `pyproject.toml`                |
| Backend  | MyPy       | Type Checking          | `pyproject.toml`                |
| Backend  | pytest     | Testing                | `pyproject.toml`                |
| Backend  | Hypothesis | Property-based Testing | `pyproject.toml`                |
| Backend  | Bandit     | Security Scanning      | (via Ruff S rules)              |
| Backend  | Vulture    | Dead Code Detection    | `vulture_whitelist.py`          |
| Backend  | Radon      | Complexity Metrics     | (CLI args)                      |
| Frontend | ESLint     | Linting                | `frontend/eslint.config.mjs`    |
| Frontend | Prettier   | Formatting             | `frontend/package.json`         |
| Frontend | TypeScript | Type Checking          | `frontend/tsconfig.json`        |
| Frontend | Vitest     | Testing                | `frontend/vite.config.ts`       |
| Frontend | Playwright | E2E Testing            | `frontend/playwright.config.ts` |
| Frontend | Knip       | Dead Code Detection    | `frontend/package.json`         |
| Both     | Hadolint   | Dockerfile Linting     | `.pre-commit-config.yaml`       |
| Both     | Semgrep    | Security Scanning      | `semgrep.yml`                   |

## Backend Tools (Python)

### Ruff - Linting and Formatting

[Ruff](https://docs.astral.sh/ruff/) is an extremely fast Python linter and formatter written in Rust.

**Configuration** (`pyproject.toml`):

```toml
[tool.ruff]
target-version = "py314"
line-length = 100
src = ["backend"]

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort (import sorting)
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "ARG",    # flake8-unused-arguments
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking
    "PTH",    # flake8-use-pathlib
    "ERA",    # eradicate (commented-out code)
    "PL",     # Pylint
    "RUF",    # Ruff-specific rules
    "ASYNC",  # flake8-async
    "S",      # flake8-bandit (security)
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

**Commands:**

```bash
# Check for linting errors
uv run ruff check backend/

# Auto-fix linting errors
uv run ruff check --fix backend/

# Check formatting
uv run ruff format --check backend/

# Auto-format code
uv run ruff format backend/
```

### MyPy - Type Checking

[MyPy](https://mypy.readthedocs.io/) performs static type checking on Python code.

**Configuration** (`pyproject.toml`):

```toml
[tool.mypy]
python_version = "3.14"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
ignore_missing_imports = true
plugins = ["pydantic.mypy"]
```

**Commands:**

```bash
# Run type checking
uv run mypy backend/

# Run with specific options
uv run mypy backend/ --ignore-missing-imports
```

### pytest - Testing Framework

[pytest](https://docs.pytest.org/) is the testing framework used for all backend tests.

**Configuration** (`pyproject.toml`):

```toml
[tool.pytest.ini_options]
testpaths = ["backend/tests"]
python_files = ["test_*.py"]
asyncio_mode = "auto"
addopts = "-n auto --dist=worksteal -v --strict-markers --tb=short"
timeout = 5
markers = [
    "asyncio: mark test as an async test",
    "unit: mark test as a unit test",
    "integration: mark test as an integration test (5s timeout)",
    "e2e: mark test as an end-to-end pipeline test",
    "gpu: mark test as a GPU test",
    "slow: mark test as legitimately slow (30s timeout)",
    "benchmark: mark test as a benchmark test",
    "serial: mark test as requiring serial execution",
]
```

**Commands:**

```bash
# Run all tests
uv run pytest backend/tests/

# Run unit tests with parallel execution
uv run pytest backend/tests/unit/ -n auto --dist=worksteal

# Run integration tests (serial execution)
uv run pytest backend/tests/integration/ -n0

# Run with coverage
uv run pytest backend/tests/ --cov=backend --cov-report=term-missing

# Run specific test file
uv run pytest backend/tests/unit/test_cameras.py -v

# Run tests matching a pattern
uv run pytest -k "test_camera" -v
```

### Hypothesis - Property-Based Testing

[Hypothesis](https://hypothesis.readthedocs.io/) generates test cases automatically based on property specifications.

**Configuration** (`pyproject.toml`):

```toml
[tool.hypothesis.profiles.ci]
max_examples = 100
deadline = 1000
database = "none"
print_blob = true

[tool.hypothesis.profiles.dev]
max_examples = 500
deadline = 5000
database = "directory:.hypothesis"
```

**Usage in tests:**

```python
from hypothesis import given, strategies as st

@given(st.integers(min_value=0, max_value=100))
def test_risk_score_bounds(score):
    """Property: risk scores must be bounded."""
    assert 0 <= process_risk(score) <= 100
```

### Coverage Configuration

**Configuration** (`pyproject.toml`):

```toml
[tool.coverage.run]
source = ["backend"]
omit = ["backend/tests/*", "backend/examples/*", "backend/main.py"]

[tool.coverage.report]
fail_under = 95
show_missing = true
precision = 2
```

**Coverage thresholds:**

| Test Type   | Threshold | Enforcement |
| ----------- | --------- | ----------- |
| Unit        | 85%       | CI          |
| Integration | 50%       | CI          |
| Combined    | 80%       | Local       |
| Overall     | 95%       | CI (final)  |

### Vulture - Dead Code Detection

[Vulture](https://github.com/jendrikseipp/vulture) finds unused code in Python projects.

**Commands:**

```bash
# Run dead code detection
uv run vulture backend/ --min-confidence 80

# With whitelist (for false positives)
uv run vulture backend/ vulture_whitelist.py --min-confidence 80
```

### Radon - Complexity Metrics

[Radon](https://radon.readthedocs.io/) computes code complexity metrics.

**Commands:**

```bash
# Cyclomatic complexity (show grades A-F)
uv run radon cc backend/ -a -s

# Maintainability index
uv run radon mi backend/ -s

# Only show complex functions (grade C or worse)
uv run radon cc backend/ -a -nc
```

**Complexity grades:**

| Grade | Complexity | Risk       |
| ----- | ---------- | ---------- |
| A     | 1-5        | Low        |
| B     | 6-10       | Low        |
| C     | 11-20      | Moderate   |
| D     | 21-30      | High       |
| E     | 31-40      | Very High  |
| F     | 41+        | Untestable |

## Frontend Tools (TypeScript/React)

### ESLint - Linting

[ESLint](https://eslint.org/) is the JavaScript/TypeScript linter with React-specific rules.

**Configuration** (`frontend/eslint.config.mjs`):

```javascript
// Key enabled rule sets:
// - @eslint/js recommended
// - typescript-eslint recommended + recommendedTypeChecked
// - react, react-hooks, jsx-a11y plugins
// - import ordering

// Key rules:
'@typescript-eslint/no-floating-promises': 'error',
'@typescript-eslint/await-thenable': 'error',
'react-hooks/rules-of-hooks': 'error',
'react-hooks/exhaustive-deps': 'warn',
'import/order': ['error', { 'newlines-between': 'always' }],
```

**Commands:**

```bash
cd frontend

# Run linting
npm run lint

# Auto-fix issues
npm run lint:fix
```

### Prettier - Code Formatting

[Prettier](https://prettier.io/) enforces consistent code formatting.

**Configuration** (in `frontend/package.json`):

```json
{
  "devDependencies": {
    "prettier": "^3.2.4",
    "prettier-plugin-tailwindcss": "^0.7.2"
  }
}
```

**Commands:**

```bash
cd frontend

# Check formatting
npm run format:check

# Auto-format code
npm run format
```

### TypeScript - Type Checking

TypeScript provides static type checking for the frontend.

**Configuration** (`frontend/tsconfig.json`):

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "jsx": "react-jsx"
  }
}
```

**Commands:**

```bash
cd frontend

# Run type checking
npm run typecheck

# Or directly
npx tsc --noEmit
```

### Vitest - Unit Testing

[Vitest](https://vitest.dev/) is the testing framework for frontend unit tests.

**Commands:**

```bash
cd frontend

# Run tests in watch mode
npm test

# Run tests once
npm test -- --run

# Run with coverage
npm run test:coverage

# Run with UI
npm run test:ui
```

### Playwright - E2E Testing

[Playwright](https://playwright.dev/) runs end-to-end browser tests.

**Commands:**

```bash
cd frontend

# Run all E2E tests
npm run test:e2e

# Run in headed mode (visible browser)
npm run test:e2e:headed

# Run in debug mode
npm run test:e2e:debug

# View test report
npm run test:e2e:report

# Run specific browser
npx playwright test --project=chromium
npx playwright test --project=firefox
npx playwright test --project=webkit
```

### Knip - Dead Code Detection

[Knip](https://knip.dev/) finds unused files, dependencies, and exports in TypeScript projects.

**Commands:**

```bash
cd frontend

# Run dead code detection
npm run dead-code

# Or directly
npx knip
```

## Pre-commit Hooks

Pre-commit hooks run automatically before each commit to catch issues early.

### Installation

```bash
# Install pre-commit (if not already installed)
pip install pre-commit

# Install hooks
pre-commit install

# Install pre-push hooks (for tests)
pre-commit install --hook-type pre-push
```

### Hook Configuration (`.pre-commit-config.yaml`)

| Hook                 | Stage      | Purpose                                     |
| -------------------- | ---------- | ------------------------------------------- |
| trailing-whitespace  | pre-commit | Remove trailing whitespace                  |
| end-of-file-fixer    | pre-commit | Ensure files end with newline               |
| check-yaml           | pre-commit | Validate YAML syntax                        |
| check-json           | pre-commit | Validate JSON syntax                        |
| check-merge-conflict | pre-commit | Detect merge conflict markers               |
| detect-private-key   | pre-commit | Prevent committing private keys             |
| hadolint             | pre-commit | Lint Dockerfiles                            |
| semgrep              | pre-commit | Security scanning (Python)                  |
| ruff                 | pre-commit | Python linting                              |
| ruff-format          | pre-commit | Python formatting                           |
| mypy                 | pre-commit | Python type checking                        |
| prettier             | pre-commit | Format non-frontend files                   |
| prettier-frontend    | pre-commit | Format frontend files                       |
| eslint               | pre-commit | Frontend linting                            |
| typescript-check     | pre-commit | Frontend type checking                      |
| auto-rebase          | pre-push   | Rebase on origin/main                       |
| fast-test            | pre-push   | Run unit tests                              |
| api-types-contract   | pre-push   | Verify API types are current                |
| check-test-mocks     | pre-commit | Verify integration tests mock slow services |
| check-test-timeouts  | pre-commit | Verify tests mock slow sleeps               |

### Running Hooks Manually

```bash
# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run ruff --all-files
pre-commit run mypy --all-files

# Skip hooks (emergencies only!)
SKIP=fast-test git commit -m "message"
```

## CI/CD Enforcement

All quality checks are enforced in CI (`.github/workflows/ci.yml`).

### Backend CI Jobs

| Job                       | Tool    | Blocking |
| ------------------------- | ------- | -------- |
| Backend Lint              | Ruff    | Yes      |
| Backend Type Check        | MyPy    | Yes      |
| Backend Unit Tests        | pytest  | Yes      |
| Backend Integration Tests | pytest  | Yes      |
| Dead Code Detection       | Vulture | No       |
| Complexity Check          | Radon   | No       |

### Frontend CI Jobs

| Job                        | Tool       | Blocking |
| -------------------------- | ---------- | -------- |
| Frontend Lint              | ESLint     | Yes      |
| Frontend Type Check        | TypeScript | Yes      |
| Frontend Tests             | Vitest     | Yes      |
| E2E Tests (Chromium)       | Playwright | No\*     |
| E2E Tests (Firefox/WebKit) | Playwright | No       |
| Dead Code Detection        | Knip       | No       |
| API Types Contract         | Custom     | Yes      |

\*E2E tests are temporarily non-blocking while stabilizing.

### Security CI Jobs

| Job                     | Tool    | Blocking |
| ----------------------- | ------- | -------- |
| Admin Endpoint Security | pytest  | Yes      |
| Security Scanning       | Semgrep | Yes      |

## Quick Reference Commands

### Full Validation (Recommended Before PRs)

```bash
# Run everything
./scripts/validate.sh

# Backend only
./scripts/validate.sh --backend

# Frontend only
./scripts/validate.sh --frontend
```

### Backend Quick Commands

```bash
# Lint and format
uv run ruff check --fix backend/ && uv run ruff format backend/

# Type check
uv run mypy backend/

# Run tests
uv run pytest backend/tests/ -v

# Run tests with coverage
uv run pytest backend/tests/ --cov=backend --cov-report=term-missing
```

### Frontend Quick Commands

```bash
cd frontend

# Lint and format
npm run lint:fix && npm run format

# Type check
npm run typecheck

# Run tests
npm test -- --run

# Run E2E tests
npm run test:e2e
```

### All Pre-commit Hooks

```bash
pre-commit run --all-files
```

## Troubleshooting

### Ruff Errors

```bash
# See what rules are being violated
uv run ruff check backend/ --show-source

# Auto-fix with unsafe fixes
uv run ruff check --fix --unsafe-fixes backend/
```

### MyPy Errors

```bash
# Show detailed error messages
uv run mypy backend/ --show-error-codes

# Generate stubs for missing packages
uv run stubgen -p package_name
```

### ESLint Errors

```bash
# See rule documentation
npx eslint --print-config src/App.tsx

# Disable rule for specific line
// eslint-disable-next-line @typescript-eslint/no-explicit-any
```

### TypeScript Errors

```bash
# See compiler diagnostics
npx tsc --noEmit --diagnostics

# Generate declaration files to debug types
npx tsc --declaration --emitDeclarationOnly
```

## Related Documentation

- [Contributing Guide](contributing.md) - Development workflow
- [Testing Guide](testing.md) - Test strategy and patterns
- [Setup Guide](setup.md) - Development environment setup
- [CLAUDE.md](../../CLAUDE.md) - Project instructions
