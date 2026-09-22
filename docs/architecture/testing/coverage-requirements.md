# Coverage Requirements

This document specifies the test coverage requirements enforced in CI/CD pipelines for both backend and frontend code.

## Overview

Coverage gates ensure code quality by requiring minimum test coverage before merging. The enforced model (as of the 2026-09 docs scan):

- **Backend absolute floor**: 80% combined (unit + integration), executed by
  `scripts/validate.sh --fail-under=80` and mirrored in
  `.github/workflows/nightly-full-gate.yml`
- **Backend PR diff gate**: `pyproject.toml` `fail_under = 85` is the PR diff
  gate's _relative_ baseline over merged shard data (owner ruling A7.1,
  2026-09-19) — not an absolute floor; the diff gate forgives drops up to its
  0.5pp noise band
- **Per-tier floors**: unit 84 / integration 37, enforced in the CI merge
  steps only when the tier fully passed
- **Frontend**: measured floors 80 (statements) / 74.6 (branches) /
  78.4 (functions) / 80.9 (lines), enforced by
  `frontend/scripts/merge-shard-coverage.mjs --enforce` in CI only when all
  Vitest shards passed (R-1/WP2.3: declared floors must equal measured values)

Measured backend coverage 2026-09-20: 84.12% blended / 86.02% line /
76.27% branch — the three are different numbers; `--format=total` is the
blend.

## Backend Coverage

### Configuration

From `pyproject.toml:529-568`:

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
# Owner ruling A7.1 (2026-09-19): this 85 is the WP0.9 PR diff gate's
# RELATIVE baseline — NOT an absolute floor. The executed absolute backend
# floor is 80 on combined unit+integration (validate.sh / nightly-full-gate).
fail_under = 85
show_missing = true
precision = 2

[tool.coverage.html]
directory = "coverage/backend"
```

### Coverage Gates

| Metric                        | Threshold         | Enforcement                                                                         |
| ----------------------------- | ----------------- | ----------------------------------------------------------------------------------- |
| Combined (unit + integration) | 80%               | Absolute floor — `validate.sh --fail-under=80`, mirrored in `nightly-full-gate.yml` |
| PR diff gate baseline         | 85 (`fail_under`) | RELATIVE baseline over merged shard data (owner ruling A7.1); 0.5pp noise band      |
| Unit tier                     | 84                | CI merge step, only when the unit tier fully passed                                 |
| Integration tier              | 37                | CI merge step, only when the integration tier fully passed                          |
| Branch coverage               | Measured          | Main publishes line and branch separately                                           |

### Running Coverage

```bash
# Unit tests with coverage
uv run pytest backend/tests/unit/ --cov=backend --cov-report=term-missing

# Combined coverage (what the 80% absolute gate measures)
./scripts/validate.sh

# HTML report
uv run pytest backend/tests/ --cov=backend --cov-report=html
# Open coverage/backend/index.html in browser

# XML report (for CI)
uv run pytest backend/tests/ --cov=backend --cov-report=xml
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

Required code coverage of 80.00% reached. Total 84.12%
```

### Excluded Files

Files excluded from coverage (from `pyproject.toml:532-546`):

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

Lines excluded from coverage (from `pyproject.toml:549-556`):

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

Coverage is configured in `frontend/vite.config.ts` (`test.coverage`,
provider `v8`), with floors set AT the measured values (WP2.3 / R-1):

```typescript
thresholds: {
  // Floors are the merged-shard MEASURED values (run 35486259345,
  // 2026-09-20), mirrored by merge-shard-coverage.mjs's FLOORS.
  statements: 80,
  branches: 74.6,
  functions: 78.4,
  lines: 80.9,
},
```

### Coverage Gates

| Metric     | Threshold | Enforcement                                               |
| ---------- | --------- | --------------------------------------------------------- |
| Statements | 80        | `merge-shard-coverage.mjs --enforce` on merged shard data |
| Branches   | 74.6      | same                                                      |
| Functions  | 78.4      | same                                                      |
| Lines      | 80.9      | same                                                      |

CI runs the merge step (`ci.yml` "Merge frontend coverage") with `--enforce`
only when every Vitest shard passed — partial shard data is merged for the
record but floors are not enforced against it.

### Running Coverage

```bash
cd frontend

# Run tests with coverage (vitest --coverage)
npm run test:coverage

# Watch mode with coverage
npm run test:coverage -- --watch

# HTML report (per vite config: ./coverage)
npm run test:coverage -- --coverage.reporter=html
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

### Backend CI (`.github/workflows/ci.yml`)

Backend tests run as sharded jobs; coverage is collected with
`--cov-fail-under=0` in the test steps and enforced AFTER merging shard data:

- `unit-tests` → `unit-tests-coverage-merge` → `unit-tests-summary`
- `integration-tests-{api,websocket,services,models}` →
  `integration-coverage-merge` → `integration-tests-summary`
- The merge steps combine per-shard `.coverage` files, publish line and
  branch percentages, and diff against the `fail_under = 85` relative
  baseline (WP0.9 diff gate, 0.5pp noise band). Per-tier absolute floors
  (unit 84 / integration 37) are enforced in the merge steps only when the
  tier fully passed.

### Frontend CI

- `frontend-tests` runs Vitest shards (coverage collected per shard)
- `frontend-coverage-merge` runs
  `node frontend/scripts/merge-shard-coverage.mjs coverage-reports/ --out
coverage-merged --enforce` — enforcement flag applied only when
  `needs.frontend-tests.result == 'success'` (never gate floors on partial
  shard data)

### Nightly Full Gate

`.github/workflows/nightly-full-gate.yml` runs the absolute combined gate
(`--fail-under=80` on merged unit+integration coverage) — the same contract
as `./scripts/validate.sh`.

### Validation Script

`./scripts/validate.sh` is the local mirror of the CI coverage contract:

```bash
# What it does (scripts/validate.sh, coverage sections):
# 1. Unit tests:     coverage written to a shard data file with
#                    --cov-fail-under=0 (so pyproject's fail_under=85
#                    cannot fire early on partial data)
# 2. Integration:    same, separate data file
# 3. coverage combine → report gated at 80% on the merged data
# 4. Frontend:       cd frontend && npm run test:coverage
```

`./scripts/validate.sh --fast` skips the coverage proof entirely
(change-scoped advisory tier).

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

From `pyproject.toml:633-650` (mutmut 3.x — the old 2.x-era
`paths_to_mutate`/`tests_dir` keys are deprecated and no longer used):

```toml
[tool.mutmut]
# Denominator: every service + API-route module (mutmut 3's name for the
# deprecated paths_to_mutate). Tests are excluded by construction.
source_paths = [
    "backend/services",
    "backend/api/routes",
]
# Test selection = every backend UNIT test (selection is per-mutant anyway)
pytest_add_cli_args_test_selection = [
    "backend/tests/unit",
]
```

Running mutation tests (canonical runner is `scripts/mutation-run.sh`;
per-module scores come from `scripts/mutation-score.py`):

```bash
# Full widened set
./scripts/mutation-run.sh

# One module's mutants
./scripts/mutation-run.sh severity

# View surviving mutants
uv run mutmut results

# Show a specific mutant
uv run mutmut show <mutant_key>
```

Mutation testing creates small changes (mutants) in your code and verifies
that tests catch them. A high "mutation score" indicates effective tests.
`mutate_only_covered_lines = true` keeps the denominator honest (mutants in
uncovered lines are surfaced separately by `mutation-score.py`).

## Related Documentation

- [Unit Testing](unit-testing.md) - Backend unit test patterns
- [Integration Testing](integration-testing.md) - Integration test patterns
- [E2E Testing](e2e-testing.md) - End-to-end testing
- [Test Fixtures](test-fixtures.md) - Factory patterns
