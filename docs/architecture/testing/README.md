# Testing Hub

This hub documents the comprehensive testing infrastructure for the AI-powered home security monitoring system. The system follows **Test-Driven Development (TDD)** practices with a multi-layered testing strategy.

## Test Pyramid

```
                    /\
                   /  \
                  / E2E \              < 2% - Critical user flows
                 /--------\
                / Contract  \          < 5% - API contracts, WebSocket messages
               /  Security   \
              /---------------\
             /   Integration   \       ~15% - Multi-component workflows
            /-------------------\
           /        Unit         \     ~80% - Isolated component testing
          /-----------------------\
```

## Documentation Index

| Document                                          | Purpose                                       |
| ------------------------------------------------- | --------------------------------------------- |
| [Unit Testing](unit-testing.md)                   | pytest patterns, fixtures, mocking strategies |
| [Integration Testing](integration-testing.md)     | Database tests, API tests, parallel execution |
| [E2E Testing](e2e-testing.md)                     | Playwright patterns, Page Object Model        |
| [Test Fixtures](test-fixtures.md)                 | Factory patterns, Hypothesis strategies       |
| [Coverage Requirements](coverage-requirements.md) | Coverage gates, CI enforcement                |

## Quick Reference

### Running Tests

```bash
# Full validation (recommended before PRs)
./scripts/validate.sh

# Backend unit tests (parallel)
uv run pytest backend/tests/unit/ -n auto --dist=worksteal

# Backend integration tests (parallel with worker isolation)
uv run pytest backend/tests/integration/ -n8 --dist=worksteal

# Frontend tests
cd frontend && npm test

# E2E tests (Playwright)
cd frontend && npx playwright test
```

### Test Structure

```
backend/tests/
  conftest.py              # Root fixtures (database, Redis, HTTP client)
  factories.py             # factory_boy test data factories
  hypothesis_strategies.py # Hypothesis strategies for property-based testing
  strategies.py            # Additional domain-specific strategies
  unit/                    # 300+ test files - isolated component testing
  integration/             # 109+ test files - multi-component workflows
  e2e/                     # Pipeline integration tests
  benchmarks/              # Performance regression detection
  chaos/                   # Chaos engineering failure tests
  contracts/               # API contract validation
  security/                # Security vulnerability tests
  gpu/                     # GPU service integration tests

frontend/
  src/__tests__/           # Vitest component/hook tests
  tests/e2e/               # Playwright E2E tests
    fixtures/              # API mocks, test data
    pages/                 # Page Object Model
    specs/                 # Test specifications
```

### Coverage Requirements

| Test Type           | Minimum | Enforcement |
| ------------------- | ------- | ----------- |
| Backend Unit        | 85%     | CI gate     |
| Backend Combined    | 90%     | CI gate     |
| Frontend Statements | 83%     | CI gate     |
| Frontend Branches   | 77%     | CI gate     |
| Frontend Functions  | 81%     | CI gate     |
| Frontend Lines      | 84%     | CI gate     |

### Key Configuration Files

| File                                 | Purpose                                          |
| ------------------------------------ | ------------------------------------------------ |
| `pyproject.toml:358-419`             | pytest configuration, markers, coverage settings |
| `frontend/vite.config.ts:1-102`      | Vitest configuration and coverage thresholds     |
| `frontend/playwright.config.ts:1-78` | Playwright E2E configuration                     |

## Testing Philosophy

### TDD Workflow

1. **RED**: Write a failing test that defines expected behavior
2. **GREEN**: Implement minimal code to make the test pass
3. **REFACTOR**: Improve code quality while keeping tests green

### Test Isolation

- **Unit tests**: All external dependencies mocked
- **Integration tests**: Real database, mocked Redis (per-worker isolation)
- **E2E tests**: Full stack with API mocks

### Parallel Execution

Backend tests support parallel execution via pytest-xdist:

- **Unit tests**: `-n auto --dist=worksteal` (fully parallel)
- **Integration tests**: `-n8 --dist=worksteal` (worker-isolated databases)

Each pytest-xdist worker gets its own PostgreSQL database (`security_test_gw0`, etc.) for complete isolation.

## Related Documentation

- [TDD Workflow Guide](../../development/testing-workflow.md)
- [Testing Guide](../../development/testing.md)
- [Testing Patterns](../../developer/patterns/AGENTS.md)
- [Backend Tests AGENTS.md](../../../backend/tests/AGENTS.md)
