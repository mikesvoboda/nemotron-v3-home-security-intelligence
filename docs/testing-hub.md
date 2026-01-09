# Testing Documentation Hub

**Central hub for all testing documentation in the Home Security Intelligence project.**

This hub consolidates testing guidance from CLAUDE.md, TESTING_GUIDE.md, and docs/testing/ into a single navigation point.

---

## Quick Reference

### Essential Commands

```bash
# Full validation (recommended before PRs)
./scripts/validate.sh

# Backend tests
uv run pytest backend/tests/unit/ -n auto --dist=worksteal    # Unit (~60-90s)
uv run pytest backend/tests/integration/ -n0                   # Integration (~60-90s)

# Frontend tests
cd frontend && npm test                                        # Component/hook tests
cd frontend && npx playwright test                             # E2E tests

# Coverage reports
uv run pytest backend/tests/ --cov=backend --cov-report=html
cd frontend && npm test -- --coverage
```

### Coverage Requirements

| Test Type        | Minimum Coverage | Enforcement   |
| ---------------- | ---------------- | ------------- |
| Backend Unit     | 85%              | CI gate       |
| Backend Combined | 95%              | CI gate       |
| Frontend         | 83%/77%/81%/84%  | CI gate       |
| E2E              | Critical paths   | Manual review |

**Note:** Frontend thresholds are statements/branches/functions/lines respectively.

**Full Guide:** [TESTING_GUIDE.md](./TESTING_GUIDE.md) - Comprehensive patterns, fixtures, and examples.

---

## TDD Workflow

### RED-GREEN-REFACTOR Cycle

```
+----------+     +----------+     +-----------+
|   RED    | --> |  GREEN   | --> | REFACTOR  |
|  (fail)  |     |  (pass)  |     | (improve) |
+----------+     +----------+     +-----------+
      ^                                 |
      +---------------------------------+
```

1. **RED** - Write a failing test that defines the expected behavior
2. **GREEN** - Write the minimum code necessary to make the test pass
3. **REFACTOR** - Improve the code while keeping tests green

### Pre-Implementation Checklist

Before writing any production code:

- [ ] Understand the acceptance criteria from the Linear issue
- [ ] Identify the code layer(s) involved (API, service, component, E2E)
- [ ] Write test stubs for each acceptance criterion
- [ ] Run tests to confirm they fail (RED phase)
- [ ] Only then begin implementation

### TDD Skill

For complex features, invoke the TDD skill:

```bash
/superpowers:test-driven-development
```

### Related Documentation

- **TDD_WORKFLOW.md** - `docs/testing/TDD_WORKFLOW.md` (placeholder - needs content)
- **Linear TDD Issues** - [View TDD-labeled issues](https://linear.app/nemotron-v3-home-security/team/NEM/label/tdd)

---

## Testing by Layer

### Backend Testing

#### Unit Tests (pytest)

- **Location:** `backend/tests/unit/` (8,229 tests)
- **Framework:** pytest + pytest-asyncio + Hypothesis
- **Parallelization:** `pytest-xdist` with worksteal scheduler

```bash
# Run all unit tests
uv run pytest backend/tests/unit/ -n auto --dist=worksteal

# Run by marker
pytest -m unit backend/tests/
pytest -m "unit and not slow" backend/tests/
```

**Subdirectories:**

- `api/routes/` - API route tests
- `api/schemas/` - Pydantic schema validation
- `core/` - Infrastructure (config, database, redis)
- `models/` - ORM model tests
- `services/` - Business logic and AI pipeline

#### Integration Tests (pytest)

- **Location:** `backend/tests/integration/` (1,556 tests)
- **Framework:** pytest + testcontainers
- **Parallelization:** Domain-based sharding (4 CI jobs)

```bash
# Run integration tests (serial locally)
uv run pytest backend/tests/integration/ -n0

# Run by marker
pytest -m integration backend/tests/
```

**CI Shards:**
| Shard | Domain | Filter Pattern |
|-------|--------|----------------|
| 1 | API routes | `test_*_api or test_api_*` |
| 2 | WebSocket/PubSub | `test_websocket or test_*_broadcaster` |
| 3 | Services | `test_*_integration or test_batch*` |
| 4 | Models | `test_models or test_database` |

**Documentation:** [backend/tests/AGENTS.md](../backend/tests/AGENTS.md)

---

### Frontend Testing

#### Component Tests (Vitest + React Testing Library)

- **Location:** `frontend/src/**/*.test.tsx` (~2,000+ tests)
- **Framework:** Vitest + React Testing Library
- **Pattern:** Co-located with source files

```bash
cd frontend && npm test           # Run all tests
cd frontend && npm test -- --ui   # Interactive UI
```

**Example:**

```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { RiskGauge } from './RiskGauge';

describe('RiskGauge', () => {
  it('displays low risk styling for scores under 30', () => {
    render(<RiskGauge score={25} />);
    const gauge = screen.getByRole('meter');
    expect(gauge).toHaveAttribute('aria-valuenow', '25');
    expect(gauge).toHaveClass('risk-low');
  });
});
```

#### Hook Tests

- **Location:** `frontend/src/hooks/**/*.test.ts`
- **Pattern:** Test custom hooks with `renderHook` from `@testing-library/react`

#### Documentation

- [frontend/tests/AGENTS.md](../frontend/tests/AGENTS.md) - Test suite overview
- [frontend/vite.config.ts](../frontend/vite.config.ts) - Vitest configuration

---

### E2E Testing (Playwright)

- **Location:** `frontend/tests/e2e/specs/` (~500+ tests)
- **Framework:** Playwright
- **Pattern:** Page Object Model with auto-mocked API

```bash
cd frontend && npx playwright test                    # All browsers
cd frontend && npx playwright test --project=chromium # Chromium only
cd frontend && npx playwright test --ui               # Interactive mode
```

**CI Configuration:**

- Chromium: 4 parallel shards
- Firefox/WebKit: 1 job each (non-blocking)

**Documentation:**

- [frontend/tests/e2e/AGENTS.md](../frontend/tests/e2e/AGENTS.md) - E2E overview
- [frontend/tests/e2e/fixtures/AGENTS.md](../frontend/tests/e2e/fixtures/AGENTS.md) - Mock configurations
- [frontend/tests/e2e/pages/AGENTS.md](../frontend/tests/e2e/pages/AGENTS.md) - Page objects
- [frontend/playwright.config.ts](../frontend/playwright.config.ts) - Playwright configuration

---

## Test Infrastructure

### Fixtures and Factories

**Backend fixtures** are defined in `backend/tests/conftest.py`:

| Fixture          | Scope    | Description                           |
| ---------------- | -------- | ------------------------------------- |
| `isolated_db`    | function | Isolated PostgreSQL database          |
| `session`        | function | Savepoint-based transaction isolation |
| `mock_redis`     | function | AsyncMock Redis client                |
| `client`         | function | httpx AsyncClient for API tests       |
| `camera_factory` | function | factory_boy Camera factory            |
| `event_factory`  | function | factory_boy Event factory             |

**Frontend fixtures** are defined in `frontend/tests/e2e/fixtures/`:

| Configuration         | Purpose                            |
| --------------------- | ---------------------------------- |
| `defaultMockConfig`   | Normal operation with healthy data |
| `emptyMockConfig`     | No data scenarios                  |
| `errorMockConfig`     | API failure scenarios              |
| `highAlertMockConfig` | High-risk state                    |

### Test Parallelization Strategy

| Suite               | Strategy               | CI Jobs             |
| ------------------- | ---------------------- | ------------------- |
| Backend Unit        | pytest-xdist worksteal | 1 job, auto workers |
| Backend Integration | Domain sharding        | 4 parallel jobs     |
| Frontend Vitest     | Matrix sharding        | 8 parallel shards   |
| Frontend E2E        | Playwright sharding    | 4 Chromium shards   |

**Performance improvement:** 60-70% reduction from serial execution (~25-35 min to ~8-12 min).

### CI Pipeline Integration

Tests run in GitHub Actions CI:

1. **Lint + Typecheck** (~1-2 min)
2. **Backend Unit Tests** (~1-2 min)
3. **Backend Integration Tests** (~2-3 min, 4 shards)
4. **Frontend Vitest** (~1-2 min, 8 shards)
5. **Frontend E2E** (~3-5 min, 4 shards)

**Total CI time:** ~8-12 min (parallelized)

---

## Coverage Requirements

### Thresholds

| Test Type           | Threshold | Source                      |
| ------------------- | --------- | --------------------------- |
| Backend Unit        | 85%       | `pyproject.toml`            |
| Backend Combined    | 95%       | `pyproject.toml` fail_under |
| Frontend Statements | 83%       | `vite.config.ts`            |
| Frontend Branches   | 77%       | `vite.config.ts`            |
| Frontend Functions  | 81%       | `vite.config.ts`            |
| Frontend Lines      | 84%       | `vite.config.ts`            |

### Checking Coverage

```bash
# Backend
uv run pytest backend/tests/unit/ --cov=backend --cov-report=term-missing
uv run pytest backend/tests/ --cov=backend --cov-report=html

# Frontend
cd frontend && npm test -- --coverage

# Full validation with coverage
./scripts/validate.sh --coverage
```

### If Coverage Fails

1. Identify uncovered lines in the coverage report
2. Write tests for the uncovered code paths
3. Do NOT lower coverage thresholds
4. Do NOT skip tests to pass CI

---

## Anti-Patterns

### Never Disable Testing

This rule is **non-negotiable**. Previous agents have violated this rule by:

- Moving test hooks from pre-commit to pre-push stage
- Lowering coverage thresholds to pass CI
- Commenting out or skipping failing tests
- Removing test assertions to make tests pass

**If tests are failing, FIX THE CODE or FIX THE TESTS.**

### Do NOT:

| Anti-Pattern                  | Consequence                            |
| ----------------------------- | -------------------------------------- |
| `@pytest.skip` without reason | Hides broken functionality             |
| `git commit --no-verify`      | Bypasses pre-commit checks             |
| Lower coverage thresholds     | Degrades code quality over time        |
| Comment out failing tests     | Technical debt accumulation            |
| Use `TRUNCATE TABLE` in tests | Causes deadlocks in parallel execution |
| Hard-code `time.sleep()`      | Flaky tests, slow execution            |

### Do:

| Best Practice                           | Benefit                  |
| --------------------------------------- | ------------------------ |
| Use `DELETE FROM` instead of `TRUNCATE` | Parallel-safe cleanup    |
| Use `unique_id()` for test data         | Prevents ID conflicts    |
| Use explicit timeouts                   | Prevents hanging tests   |
| Mock external services                  | Fast, reliable tests     |
| Test user-visible behavior              | Resilient to refactoring |

---

## Related Documentation

### Core Documentation

| Document                                                     | Purpose                                     |
| ------------------------------------------------------------ | ------------------------------------------- |
| [TESTING_GUIDE.md](./TESTING_GUIDE.md)                       | Comprehensive testing patterns and fixtures |
| [TEST_PERFORMANCE_METRICS.md](./TEST_PERFORMANCE_METRICS.md) | CI performance baselines                    |
| [/CLAUDE.md](../CLAUDE.md)                                   | Project instructions and TDD requirements   |

### Testing Directory (docs/testing/)

| File                                                 | Status   | Description                            |
| ---------------------------------------------------- | -------- | -------------------------------------- |
| [AGENTS.md](./testing/AGENTS.md)                     | Complete | Testing directory guide                |
| [TDD_WORKFLOW.md](./testing/TDD_WORKFLOW.md)         | **Stub** | TDD workflow (needs content)           |
| [TESTING_PATTERNS.md](./testing/TESTING_PATTERNS.md) | **Stub** | Testing patterns (needs content)       |
| [HYPOTHESIS_GUIDE.md](./testing/HYPOTHESIS_GUIDE.md) | **Stub** | Property-based testing (needs content) |

### Backend Testing

| Document                                                    | Purpose                              |
| ----------------------------------------------------------- | ------------------------------------ |
| [backend/tests/AGENTS.md](../backend/tests/AGENTS.md)       | Backend test infrastructure overview |
| [backend/tests/conftest.py](../backend/tests/conftest.py)   | Shared pytest fixtures               |
| [backend/tests/factories.py](../backend/tests/factories.py) | factory_boy factories                |

### Frontend Testing

| Document                                                                          | Purpose                |
| --------------------------------------------------------------------------------- | ---------------------- |
| [frontend/tests/AGENTS.md](../frontend/tests/AGENTS.md)                           | Frontend test overview |
| [frontend/tests/e2e/AGENTS.md](../frontend/tests/e2e/AGENTS.md)                   | E2E test architecture  |
| [frontend/tests/e2e/fixtures/AGENTS.md](../frontend/tests/e2e/fixtures/AGENTS.md) | Mock configurations    |
| [frontend/tests/e2e/pages/AGENTS.md](../frontend/tests/e2e/pages/AGENTS.md)       | Page object patterns   |

---

## Quick Links

- **Linear TDD Issues:** [View in Linear](https://linear.app/nemotron-v3-home-security/team/NEM/label/tdd)
- **CI Workflow:** `.github/workflows/ci.yml`
- **Validation Script:** `./scripts/validate.sh`
- **Test Duration Audit:** `scripts/audit-test-durations.py`
