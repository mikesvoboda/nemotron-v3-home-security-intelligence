# Testing Infrastructure Reliability Design

**Date:** 2025-01-01
**Status:** Approved
**Author:** Claude + Human collaboration

## Overview

This initiative takes a holistic approach to improving testing reliability through four parallel workstreams:

1. **Stabilize Integration Tests** - Introduce aggressive testcontainers isolation to eliminate flakiness
2. **Expand E2E Coverage** - Comprehensive Playwright tests covering all routes, interactions, and error states
3. **Fix CI Parallelization** - Resolve xdist race conditions to re-enable parallel execution
4. **Fill Unit Test Gaps** - Add model tests using traditional + property-based approaches

Additionally, we migrate to **uv** for dependency management (10-100x faster installs) and consolidate configuration to a single source of truth.

## Success Criteria

- Integration tests become blocking in CI (remove `continue-on-error: true`)
- E2E coverage increases from 19 to 100+ tests (50% to 100% route coverage)
- CI pipeline time decreases from 10-15 min to 6-8 min via parallelization
- Model unit test coverage increases from 20% to 100%
- Single config source (pyproject.toml only)

## Non-Goals

- Contract testing (out of scope for this initiative)
- Visual regression testing (future enhancement)
- Performance/load testing (separate initiative)

---

## Workstream 1: Integration Test Isolation (Testcontainers)

### Current Problem

Integration tests use a shared PostgreSQL container with advisory locks for coordination. When tests run in parallel, race conditions occur during schema creation and data setup. This causes flaky tests, forcing `continue-on-error: true` in CI.

### Solution: Module-Scoped Container Isolation

```
backend/tests/integration/
├── conftest.py                    # Shared fixtures only (no containers)
├── test_cameras_api.py            # Gets own postgres + redis
├── test_events_api.py             # Gets own postgres + redis
├── test_websocket.py              # Gets own postgres + redis
└── ...
```

### Key Changes

1. **Module-scoped containers** - Each test file spins up isolated containers at module start, tears down at module end. Tests within a module share the container (fast) but are transaction-isolated (savepoints).

2. **Lazy container startup** - Containers only start when that test file runs. Unused test files don't pay startup cost.

3. **Parallel-safe by design** - No advisory locks needed. Each pytest-xdist worker can run different test modules simultaneously without conflicts.

4. **Deterministic readiness checks** - Replace `time.sleep()` with polling loops that check actual service readiness (`pg_isready`, `redis-cli ping`).

### Expected Impact

- Eliminates 100% of cross-test race conditions
- Enables `continue-on-error: false` for integration tests in CI
- Slight increase in total container count, but parallelization compensates

---

## Workstream 2: E2E Test Expansion (Playwright)

### Current Problem

19 tests across 3 files with duplicated `setupApiMocks()` in each. Only 4/8 routes tested. No page objects, making tests brittle.

### New Structure

```
frontend/tests/e2e/
├── fixtures/
│   ├── api-mocks.ts              # Shared mock responses
│   ├── test-data.ts              # Cameras, events, alerts data
│   └── websocket-mock.ts         # WebSocket simulation helper
├── pages/
│   ├── BasePage.ts               # Common selectors, wait helpers
│   ├── DashboardPage.ts          # Dashboard-specific interactions
│   ├── TimelinePage.ts           # Event timeline interactions
│   ├── AlertsPage.ts             # Alert management
│   ├── EntitiesPage.ts           # Entity listing
│   ├── AuditPage.ts              # Audit log viewing
│   ├── SystemPage.ts             # System monitoring
│   └── SettingsPage.ts           # Settings forms
├── specs/
│   ├── smoke.spec.ts             # Basic load tests (existing)
│   ├── navigation.spec.ts        # Route transitions (existing)
│   ├── realtime.spec.ts          # WebSocket tests (expand)
│   ├── dashboard.spec.ts         # Dashboard interactions (new)
│   ├── events.spec.ts            # Event workflows (new)
│   ├── alerts.spec.ts            # Alert CRUD + dismissal (new)
│   ├── entities.spec.ts          # Entity browsing (new)
│   ├── audit.spec.ts             # Audit log filtering (new)
│   ├── system.spec.ts            # System monitoring (new)
│   ├── settings.spec.ts          # Settings interactions (new)
│   ├── error-handling.spec.ts    # API failures, recovery (new)
│   └── responsive.spec.ts        # Mobile/tablet viewports (new)
└── playwright.config.ts          # Add webkit, firefox projects
```

### Test Categories (Target ~100+ Tests)

| Category               | Test Count    |
| ---------------------- | ------------- |
| Smoke/Navigation       | 12 (existing) |
| Dashboard interactions | 15            |
| Event workflows        | 20            |
| Alerts/Entities/Audit  | 25            |
| System/Settings        | 15            |
| Error handling         | 10            |
| Responsive viewports   | 10            |
| **Total**              | **107**       |

---

## Workstream 3: CI Parallelization (xdist Fix)

### Current Problem

pytest-xdist disabled in CI (`-n0`) due to `loadgroup` scheduler race conditions. Tests run serially, taking 10-15 minutes.

### Root Cause

The `--dist=loadgroup` scheduler has known issues with fixture teardown ordering when tests share database resources. Combined with advisory locks for schema coordination, this creates deadlocks.

### Solution: Three-Part Fix

#### 1. Switch scheduler to `worksteal`

```toml
# pyproject.toml
addopts = "-n auto --dist=worksteal -v --strict-markers"
```

The `worksteal` scheduler is more robust - workers steal tests from busy workers rather than pre-distributing. Avoids the loadgroup ordering bugs.

#### 2. Remove advisory locks

With module-scoped testcontainers (Workstream 1), each test module has isolated databases. No coordination needed between workers.

#### 3. Add test isolation markers for special cases

```python
# Tests that must run serially (rare)
@pytest.mark.xdist_group("serial")
def test_something_that_modifies_global_state():
    ...
```

### Configuration Consolidation

Delete `pytest.ini` and use `pyproject.toml` as single source of truth:

```toml
[tool.pytest.ini_options]
testpaths = ["backend/tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
addopts = "-n auto --dist=worksteal -v --strict-markers --timeout=5"
timeout_method = "thread"
markers = [
    "unit: unit test (default 1s timeout)",
    "integration: integration test (5s timeout)",
    "slow: slow test (30s timeout)",
    "gpu: GPU test (self-hosted runner)",
]
```

### Expected Impact

- CI time reduction: 10-15 min to 6-8 min
- Reliable parallel execution in CI
- Single config file (delete pytest.ini)

---

## Workstream 4: Model Unit Tests (Traditional + Hypothesis)

### Current Problem

Only 2/10 models have unit tests (Audit, Baseline). Critical models like Camera, Detection, Event, Zone, Alert, APIKey are untested.

### New Structure

```
backend/tests/unit/models/
├── conftest.py                   # Shared model fixtures
├── test_camera.py                # Camera model tests
├── test_detection.py             # Detection model tests
├── test_event.py                 # Event model tests
├── test_zone.py                  # Zone model tests
├── test_alert.py                 # Alert + AlertRule tests
├── test_api_key.py               # APIKey model tests
├── test_gpu_stats.py             # GPUStats model tests
└── test_enums.py                 # Enum validation tests
```

### Traditional Tests (Per Model)

- Default values and required fields
- Field validation (types, constraints, ranges)
- Relationship loading (lazy vs eager)
- Serialization (to_dict, from_dict if applicable)
- Edge cases (null handling, empty strings, boundary values)

### Property-Based Tests (Hypothesis)

```python
from hypothesis import given, strategies as st

class TestDetectionProperties:
    @given(
        confidence=st.floats(min_value=0.0, max_value=1.0),
        bbox=st.tuples(
            st.floats(0, 1), st.floats(0, 1),
            st.floats(0, 1), st.floats(0, 1)
        )
    )
    def test_detection_confidence_bounds(self, confidence, bbox):
        """Any valid confidence should be accepted."""
        detection = Detection(confidence=confidence, bbox=bbox, ...)
        assert 0 <= detection.confidence <= 1

    @given(st.builds(Detection, ...))
    def test_detection_roundtrip_serialization(self, detection):
        """Serialize then deserialize should equal original."""
        data = detection.to_dict()
        restored = Detection.from_dict(data)
        assert restored == detection
```

### Target Coverage

- 10-15 traditional tests per model (explicit cases)
- 3-5 property-based tests per model (invariants, edge cases)
- ~100 new model tests total

---

## uv Migration

### Current State

- `pip` + `venv` for dependency management
- `backend/requirements.txt` and `backend/requirements-prod.txt`
- CI installs via `pip install -r requirements.txt`
- No lock file (non-deterministic installs)

### New Structure

```
project-root/
├── pyproject.toml                # Dependencies move here
├── uv.lock                       # Deterministic lock file (auto-generated)
├── .python-version               # Pin Python version (3.14)
└── backend/
    ├── requirements.txt          # DELETE
    └── requirements-prod.txt     # DELETE
```

### pyproject.toml Dependencies

```toml
[project]
name = "home-security-intelligence"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = [
    "fastapi>=0.128.0",
    "uvicorn>=0.40.0",
    "sqlalchemy>=2.0.45",
    "asyncpg>=0.31.0",
    "redis>=7.1.0",
    "pydantic>=2.12.5",
    "pydantic-settings>=2.12.0",
    # ... rest of production deps
]

[project.optional-dependencies]
dev = [
    "pytest>=9.0.0",
    "pytest-asyncio>=1.3.0",
    "pytest-xdist>=3.8.0",
    "pytest-cov>=7.0.0",
    "hypothesis>=6.100.0",
    "ruff>=0.14.10",
    "mypy>=1.19.0",
    # ... rest of dev deps
]
```

### Command Migration

| Old (pip)                         | New (uv)              |
| --------------------------------- | --------------------- |
| `python -m venv .venv`            | `uv venv`             |
| `pip install -r requirements.txt` | `uv sync`             |
| `pip install -e ".[dev]"`         | `uv sync --dev`       |
| `pip freeze > requirements.txt`   | `uv lock` (automatic) |

### CI Changes

```yaml
- name: Install uv
  uses: astral-sh/setup-uv@v4

- name: Install dependencies
  run: uv sync --dev --frozen # Uses uv.lock, fails if out of sync
```

### Expected Impact

- CI install time: ~60s to ~5s (10x faster)
- Deterministic builds via `uv.lock`
- Single dependency source (pyproject.toml)

---

## Implementation Phases

### Phase 1: Foundation (Do First)

- Migrate to uv (enables faster iteration on subsequent phases)
- Consolidate pytest config to pyproject.toml (delete pytest.ini)
- Add Hypothesis to dev dependencies

### Phase 2: Parallel Workstreams (Can Run Concurrently)

| Workstream         | Tasks                                                                                   | Dependencies |
| ------------------ | --------------------------------------------------------------------------------------- | ------------ |
| 2A: Testcontainers | Refactor integration test fixtures, add module-scoped containers, remove advisory locks | Phase 1      |
| 2B: E2E Expansion  | Create page objects, extract fixtures, write new spec files                             | Phase 1      |
| 2C: Model Tests    | Create model test files, write traditional + property-based tests                       | Phase 1      |

### Phase 3: CI Optimization (After Phase 2A)

- Switch xdist to `worksteal` scheduler
- Re-enable `-n auto` in CI
- Remove `continue-on-error: true` from integration tests
- Verify parallel execution is stable

### Phase 4: Validation & Cleanup

- Run full test suite multiple times to verify stability
- Update CLAUDE.md and AGENTS.md documentation
- Delete obsolete files (pytest.ini, requirements.txt)
- Measure and document CI time improvements

### Estimated Effort

| Phase    | Effort | Duration (parallel agents) |
| -------- | ------ | -------------------------- |
| Phase 1  | Small  | 1 session                  |
| Phase 2A | Medium | 2-3 sessions               |
| Phase 2B | Large  | 3-4 sessions               |
| Phase 2C | Medium | 2-3 sessions               |
| Phase 3  | Small  | 1 session                  |
| Phase 4  | Small  | 1 session                  |

**Total: ~6-8 sessions with parallel execution of Phase 2 workstreams**

---

## Summary

| Metric                     | Before                      | After                    |
| -------------------------- | --------------------------- | ------------------------ |
| Integration test stability | Flaky (non-blocking)        | Deterministic (blocking) |
| E2E test coverage          | 19 tests, 50% routes        | 100+ tests, 100% routes  |
| CI parallelization         | Disabled (`-n0`)            | Enabled (`worksteal`)    |
| CI pipeline time           | 10-15 min                   | 6-8 min                  |
| Model unit tests           | 20% coverage                | 100% coverage            |
| Dependency management      | pip + requirements.txt      | uv + uv.lock             |
| Config files               | pytest.ini + pyproject.toml | pyproject.toml only      |

### New Dependencies

- `hypothesis` - Property-based testing
- `uv` - Fast dependency management (replaces pip)

### Files to Delete

- `pytest.ini`
- `backend/requirements.txt`
- `backend/requirements-prod.txt`

### Success Metrics

- Integration tests pass 100% of runs (currently ~90%)
- Zero `continue-on-error` in CI
- E2E catches regressions before production
- New contributors can trust test results
