---
title: Coverage Reporting and Analysis
source_refs:
  - pyproject.toml:195
  - codecov.yml:1
  - scripts/coverage-analysis.py:1
  - .github/workflows/ci.yml:67
---

# Coverage Reporting and Analysis

This document describes the test coverage requirements, thresholds, analysis tools, and trend tracking for the Home Security Intelligence project.

## Overview

Coverage is enforced at several independent levels. The numbers below were
re-measured 2026-09-20/21 (see [Testing Guide](testing.md) for the full
derivation); do not treat any of them as aspirational targets.

- **Combined (unit + integration):** 80% absolute floor — the only executed
  absolute backend gate (`scripts/validate.sh` `--fail-under=80`, mirrored in
  `nightly-full-gate.yml`).
- **Backend unit tier (CI):** absolute floor 84, enforced in
  `unit-tests-coverage-merge` only when every unit shard passed.
- **Backend integration tier (CI):** absolute floor 37, enforced in
  `integration-coverage-merge` only when every integration shard passed.
- **PR diff gate:** `pyproject.toml` `fail_under = 85` is the diff gate's
  RELATIVE baseline over merged shard data (owner ruling A7.1), not an
  absolute floor; a drop of up to 0.5pp is tolerated as noise
  (`scripts/check-test-coverage-gate.py`).
- **Codecov:** project target 85%, patch target 80%, critical paths 90%
  (`codecov.yml`).
- **Frontend (Vitest):** floors 80 statements / 74.6 branches / 78.4
  functions / 80.9 lines (measured, R-1; `frontend/vite.config.ts`
  `coverage.thresholds`, enforced by
  `frontend/scripts/merge-shard-coverage.mjs --enforce` in CI when all shards
  passed).

## Coverage Thresholds

### Backend Coverage

| Gate                   | Value         | Enforcement                                                         | Configuration                      |
| ---------------------- | ------------- | ------------------------------------------------------------------- | ---------------------------------- |
| Combined (abs. floor)  | 80%           | `validate.sh` + `nightly-full-gate.yml`                             | `scripts/validate.sh`              |
| Unit tier (abs. floor) | 84            | `unit-tests-coverage-merge` in CI, only when all unit shards passed | `.github/workflows/ci.yml`         |
| Integration tier floor | 37            | `integration-coverage-merge` in CI, only when all shards passed     | `.github/workflows/ci.yml`         |
| PR diff baseline       | 85 (relative) | `check-test-coverage-gate.py`, 0.5pp noise band                     | `pyproject.toml` `fail_under = 85` |
| Codecov project        | 85%           | Codecov status check                                                | `codecov.yml`                      |
| Codecov patch          | 80%           | Codecov status check                                                | `codecov.yml`                      |
| Codecov critical paths | 90%           | Codecov status check                                                | `codecov.yml`                      |

### Frontend Coverage

Floors are MEASURED values (R-1); enforcement runs in CI only when every
Vitest shard passed.

| Metric     | Threshold | Configuration             |
| ---------- | --------- | ------------------------- |
| Statements | 80%       | `frontend/vite.config.ts` |
| Branches   | 74.6%     | `frontend/vite.config.ts` |
| Functions  | 78.4%     | `frontend/vite.config.ts` |
| Lines      | 80.9%     | `frontend/vite.config.ts` |

### Critical Paths

Codecov requires **90%+ coverage** on these paths (see the `critical-paths`
status in `codecov.yml`):

```
backend/api/routes/     # REST API endpoints
backend/services/       # Business logic and AI pipeline
backend/core/security.py
backend/core/auth.py
frontend/src/hooks/
frontend/src/services/
```

## Coverage Tools

### Backend Coverage

The backend uses `pytest-cov` with Coverage.py:

```bash
# Generate coverage report
uv run pytest backend/tests/ --cov=backend --cov-report=xml --cov-report=html

# View HTML report
open coverage/backend/index.html

# Terminal report with missing lines
uv run pytest backend/tests/ --cov=backend --cov-report=term-missing
```

Configuration is in `pyproject.toml`:

```toml
[tool.coverage.run]
branch = true
source = ["backend"]
omit = [
    "backend/tests/*",
    "backend/examples/*",
    "backend/main.py",
    # Post-MVP features
    "backend/api/routes/alerts.py",
    "backend/api/routes/audit.py",
    # ...
]

[tool.coverage.report]
# RELATIVE baseline for the PR diff gate (owner ruling A7.1), not an
# absolute floor. The executed absolute backend floor is 80% combined in
# scripts/validate.sh.
fail_under = 85
show_missing = true
```

### Frontend Coverage

The frontend uses Vitest's built-in coverage:

```bash
cd frontend
npm run test:coverage
```

### Codecov Integration

Codecov provides PR comments, badge updates, and historical tracking:

- **PR Comments:** Show coverage changes for each pull request
- **Status Checks:** Block PRs that reduce coverage below thresholds
- **Badges:** Display current coverage in README

Configuration is in `codecov.yml`.

## Coverage Analysis Script

The `scripts/coverage-analysis.py` script provides detailed per-module coverage analysis:

### Basic Usage

```bash
# Analyze coverage from XML report
python scripts/coverage-analysis.py coverage.xml

# Generate JSON report
python scripts/coverage-analysis.py coverage.xml --output coverage-report.json

# Track coverage trends
python scripts/coverage-analysis.py coverage.xml --trend-file coverage-trend.json

# List uncovered lines
python scripts/coverage-analysis.py --list-uncovered coverage.xml

# Fail if coverage is below threshold
python scripts/coverage-analysis.py coverage.xml --fail-under 85
```

### Environment Variables

| Variable           | Default | Description                    |
| ------------------ | ------- | ------------------------------ |
| COVERAGE_THRESHOLD | 85.0    | Minimum coverage percentage    |
| CRITICAL_THRESHOLD | 90.0    | Coverage for critical paths    |
| WARNING_THRESHOLD  | 90.0    | Percentage to trigger warnings |

### Output Example

```
======================================================================
COVERAGE ANALYSIS REPORT
======================================================================

Configuration:
  Coverage threshold: 85.0%
  Critical path threshold: 90.0%
  Warning threshold: 90.0%

OVERALL COVERAGE:
----------------------------------------
  Line coverage:   96.42%
  Branch coverage: 89.15%

CRITICAL PATH FAILURES (2 modules below 90.0%):
----------------------------------------
  87.5% | backend.services.batch_aggregator
         234/267 lines covered
         Uncovered lines: 45, 67, 89, 112...
  88.2% | backend.api.routes.events
         156/177 lines covered

MODULES BELOW 85% THRESHOLD (1 modules):
----------------------------------------
  72.3% | backend.core.tls
         89/123 lines covered

RECOMMENDATIONS:
----------------------------------------
  1. URGENT: Address critical path coverage gaps first
     These modules contain security-critical and core business logic
     - backend.services.batch_aggregator: needs +2.5% coverage
     - backend.api.routes.events: needs +1.8% coverage

  2. Prioritize testing for lowest-coverage modules:
     - backend.core.tls: needs +12.7% coverage
```

### Trend Tracking

The script can track coverage trends over time:

```bash
# Update trend file with current coverage
python scripts/coverage-analysis.py coverage.xml --trend-file coverage-trend.json

# Output includes trend analysis
COVERAGE TREND:
----------------------------------------
  Status: improvement
  Line coverage change: +1.25%
  Branch coverage change: +0.50%
  Module gap change: -2
  Data points: 15
```

The trend file is JSON format:

```json
[
  {
    "timestamp": "2025-01-05T12:00:00+00:00",
    "commit_sha": "abc123",
    "branch": "main",
    "total_line_rate": 0.9642,
    "total_branch_rate": 0.8915,
    "modules_below_threshold": 3,
    "critical_below_threshold": 1
  }
]
```

### CI Integration

The script automatically writes GitHub Actions job summaries when `GITHUB_STEP_SUMMARY` is set:

```yaml
- name: Analyze Coverage
  run: |
    python scripts/coverage-analysis.py coverage.xml \
      --trend-file coverage-trend.json \
      --fail-under 85
```

## Generating Coverage Reports

### Full Coverage Report

```bash
# Backend coverage with XML and HTML reports
uv run pytest backend/tests/ \
  --cov=backend \
  --cov-report=xml:coverage.xml \
  --cov-report=html:coverage/backend \
  --cov-report=term-missing

# Analyze the report
python scripts/coverage-analysis.py coverage.xml
```

### Per-Test-Type Coverage

```bash
# Unit tests only
uv run pytest backend/tests/unit/ --cov=backend --cov-report=xml:coverage-unit.xml

# Integration tests only
uv run pytest backend/tests/integration/ --cov=backend --cov-report=xml:coverage-integration.xml

# Combined coverage (append)
uv run pytest backend/tests/unit/ --cov=backend --cov-append
uv run pytest backend/tests/integration/ --cov=backend --cov-append --cov-report=xml
```

## Improving Coverage

### Strategy

1. **Identify gaps:** Run `scripts/coverage-analysis.py` to find modules below threshold
2. **Prioritize critical paths:** Address critical path failures first (90%+ required by Codecov)
3. **Write targeted tests:** Focus on uncovered lines reported by the script
4. **Track progress:** Use `--trend-file` to monitor improvement over time

### Common Uncovered Code

| Code Pattern        | Solution                                  |
| ------------------- | ----------------------------------------- |
| Error handlers      | Write tests that trigger the error path   |
| Edge cases          | Use property-based testing (Hypothesis)   |
| Async exceptions    | Mock failures in external services        |
| Configuration paths | Test with different environment variables |

### Exclusions

Some code is intentionally excluded from coverage:

```toml
# In pyproject.toml
[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
    "@abstractmethod",
]
```

## Related Documentation

- [Testing Guide](testing.md) - Testing philosophy and patterns
- [CI/CD Pipeline](ci-cd.md) - How coverage is enforced in CI
- [AGENTS.md](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/blob/main/AGENTS.md) - Coverage requirements in project instructions
- [Mutation Testing](../developer/patterns/mutation-testing.md) - Beyond line coverage
