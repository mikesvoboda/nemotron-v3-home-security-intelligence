# Coverage Requirements

This document specifies the test coverage requirements enforced in CI/CD pipelines for both backend and frontend code.

## Overview

Coverage gates ensure code quality by requiring minimum test coverage before merging. The project enforces:

- **Backend**: 85% unit coverage, 90% combined coverage
- **Frontend**: Multi-metric coverage (statements, branches, functions, lines)

## Backend Coverage

### Configuration

From `pyproject.toml:388-421`:

```toml
[tool.coverage.run]
branch = true
source = ["backend"]
omit = [
    "backend/tests/*",
    "backend/examples/*",
    "backend/main.py",
    "*/__pycache__/*",
    "*/.venv/*",
    "*/venv/*",
    # Post-MVP features - need tests before enabling coverage
    "backend/api/routes/alerts.py",
    "backend/api/routes/audit.py",
    "backend/services/video_processor.py",
    "backend/services/degradation_manager.py",
    # TLS certificate generation - requires system-level testing
    "backend/core/tls.py",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
    "@abstractmethod",
]
fail_under = 90
show_missing = true
precision = 2

[tool.coverage.html]
directory = "coverage/backend"
```

### Coverage Gates

| Metric                        | Threshold | Enforcement            |
| ----------------------------- | --------- | ---------------------- |
| Unit tests only               | 85%       | CI gate                |
| Combined (unit + integration) | 90%       | CI gate                |
| Branch coverage               | Required  | Measured but not gated |

### Running Coverage

```bash
# Unit tests with coverage
uv run pytest backend/tests/unit/ --cov=backend --cov-report=term-missing

# Combined coverage
uv run pytest backend/tests/ --cov=backend --cov-report=term-missing

# HTML report
uv run pytest backend/tests/ --cov=backend --cov-report=html
# Open coverage/backend/index.html in browser

# XML report (for CI)
uv run pytest backend/tests/ --cov=backend --cov-report=xml

# Check minimum coverage without running tests
uv run coverage report --fail-under=90
```

### Coverage Output Example

```
---------- coverage: platform linux, python 3.14 -----------
Name                                    Stmts   Miss Branch BrPart  Cover   Missing
-----------------------------------------------------------------------------------
backend/api/routes/analytics.py            45      2      8      1    94%   78, 92
backend/api/routes/cameras.py              67      3     12      2    93%   45, 88, 102
backend/core/database.py                   89      0     16      0   100%
backend/services/bbox_validation.py       156      0     42      0   100%
...
-----------------------------------------------------------------------------------
TOTAL                                    4523    135    892     23    95.12%

Required coverage of 90% reached. Total 95.12%
```

### Excluded Files

Files excluded from coverage (from `pyproject.toml:391-405`):

| Path                                      | Reason                        |
| ----------------------------------------- | ----------------------------- |
| `backend/tests/*`                         | Test code                     |
| `backend/examples/*`                      | Example/demo code             |
| `backend/main.py`                         | Application entry point       |
| `backend/api/routes/alerts.py`            | Post-MVP feature              |
| `backend/api/routes/audit.py`             | Post-MVP feature              |
| `backend/services/video_processor.py`     | Post-MVP feature              |
| `backend/services/degradation_manager.py` | Post-MVP feature              |
| `backend/core/tls.py`                     | System-level testing required |

### Excluded Lines

Lines excluded from coverage (from `pyproject.toml:408-415`):

| Pattern                      | Use Case                   |
| ---------------------------- | -------------------------- |
| `pragma: no cover`           | Explicitly exclude line    |
| `def __repr__`               | Debug representation       |
| `raise NotImplementedError`  | Abstract methods           |
| `if __name__ == .__main__.:` | Script entry points        |
| `if TYPE_CHECKING:`          | Type-checking imports      |
| `@abstractmethod`            | Abstract method decorators |

## Frontend Coverage

### Configuration

Coverage is configured in the Vite config with both overall and per-file thresholds.

### Coverage Gates

| Metric     | Threshold | Enforcement |
| ---------- | --------- | ----------- |
| Statements | 83%       | CI gate     |
| Branches   | 77%       | CI gate     |
| Functions  | 81%       | CI gate     |
| Lines      | 84%       | CI gate     |

### Running Coverage

```bash
cd frontend

# Run tests with coverage
npm test -- --coverage

# Watch mode with coverage
npm test -- --coverage --watch

# HTML report
npm test -- --coverage --reporter=html
# Open coverage/index.html in browser
```

### Coverage Output Example

```
----------------|---------|----------|---------|---------|-------------------
File            | % Stmts | % Branch | % Funcs | % Lines | Uncovered Line #s
----------------|---------|----------|---------|---------|-------------------
All files       |   89.45 |   82.31 |   86.72 |   90.12 |
 components/    |   91.23 |   84.56 |   88.90 |   92.34 |
  Camera.tsx    |   95.00 |   90.00 |   93.33 |   96.00 | 45, 78
  Event.tsx     |   88.46 |   80.00 |   85.71 |   89.19 | 23, 56-58
 hooks/         |   87.50 |   78.26 |   82.14 |   88.00 |
  useEvents.ts  |   85.00 |   75.00 |   80.00 |   86.00 | 34, 67-69
----------------|---------|----------|---------|---------|-------------------
```

## CI/CD Enforcement

### Backend CI Workflow

The backend CI workflow runs coverage checks on every PR:

```yaml
# .github/workflows/backend.yml (conceptual)
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.14'

      - name: Install dependencies
        run: uv sync --extra dev

      - name: Run unit tests with coverage
        run: |
          uv run pytest backend/tests/unit/ \
            -n auto --dist=worksteal \
            --cov=backend \
            --cov-report=term-missing \
            --cov-report=xml \
            --cov-fail-under=85

      - name: Run integration tests
        run: |
          uv run pytest backend/tests/integration/ \
            -n8 --dist=worksteal

      - name: Combined coverage check
        run: |
          uv run coverage report --fail-under=90
```

### Frontend CI Workflow

```yaml
# .github/workflows/frontend.yml (conceptual)
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: cd frontend && npm ci

      - name: Run tests with coverage
        run: cd frontend && npm test -- --coverage
        # Fails if coverage thresholds not met
```

### Validation Script

The `./scripts/validate.sh` script runs all coverage checks:

```bash
#!/bin/bash
set -e

echo "Running backend unit tests with coverage..."
uv run pytest backend/tests/unit/ -n auto --dist=worksteal \
    --cov=backend --cov-fail-under=85

echo "Running backend integration tests..."
uv run pytest backend/tests/integration/ -n8 --dist=worksteal

echo "Checking combined coverage..."
uv run coverage report --fail-under=90

echo "Running frontend tests..."
cd frontend && npm test -- --coverage

echo "All validation checks passed!"
```

## Improving Coverage

### Finding Uncovered Code

```bash
# Backend: Show missing lines
uv run pytest backend/tests/ --cov=backend --cov-report=term-missing

# Backend: HTML report with line-by-line highlighting
uv run pytest backend/tests/ --cov=backend --cov-report=html

# Frontend: HTML report
cd frontend && npm test -- --coverage --reporter=html
```

### Coverage Best Practices

1. **Test behavior, not implementation**

   ```python
   # Good: Test observable behavior
   def test_event_is_high_risk_when_score_above_75():
       event = EventFactory(risk_score=80)
       assert event.is_high_risk is True

   # Avoid: Testing internal implementation
   def test_internal_method_called():
       ...
   ```

2. **Don't chase 100% coverage**

   - Focus on critical paths first
   - Some code is better left untested (trivial getters, error-handling edge cases)
   - Use `pragma: no cover` for intentional exclusions

3. **Use appropriate test types**

   - Unit tests: Business logic, utilities, pure functions
   - Integration tests: Database interactions, API contracts
   - E2E tests: Critical user flows

4. **Review coverage reports regularly**
   ```bash
   # Weekly coverage report
   uv run pytest backend/tests/ --cov=backend --cov-report=html
   # Review backend/coverage/index.html
   ```

### Common Coverage Gaps

| Gap                      | Solution                                  |
| ------------------------ | ----------------------------------------- |
| Error handling branches  | Add negative test cases                   |
| Edge cases               | Use Hypothesis for property-based testing |
| Async error paths        | Test with mocked exceptions               |
| Default parameter values | Add tests with explicit defaults          |

## Mutation Testing

For higher confidence in test quality, use mutation testing:

From `pyproject.toml:478-494`:

```toml
[tool.mutmut]
paths_to_mutate = [
    "backend/services/bbox_validation.py",
    "backend/services/severity.py",
    "backend/services/prompt_parser.py",
    "backend/services/search.py",
    "backend/services/dedupe.py",
]
tests_dir = ["backend/tests/unit/services/"]
```

Running mutation tests:

```bash
# Run mutation testing
uv run mutmut run backend/services/bbox_validation.py

# View results
uv run mutmut results

# Show specific mutant
uv run mutmut show <mutant_id>
```

Mutation testing creates small changes (mutants) in your code and verifies that tests catch them. A high "mutation score" indicates effective tests.

## Related Documentation

- [Unit Testing](unit-testing.md) - Backend unit test patterns
- [Integration Testing](integration-testing.md) - Integration test patterns
- [E2E Testing](e2e-testing.md) - End-to-end testing
- [Test Fixtures](test-fixtures.md) - Factory patterns
