---
title: Testing Guide
source_refs:
  - pyproject.toml:91
  - backend/tests/conftest.py:1
  - backend/tests/AGENTS.md:1
  - backend/tests/unit/AGENTS.md:1
  - backend/tests/integration/AGENTS.md:1
  - .pre-commit-config.yaml:99
  - .github/workflows/ci.yml:67
---

# Testing Guide

This project follows a strict Test-Driven Development (TDD) approach. All features must have tests written at the time of development.

## Test Philosophy

> **ABSOLUTE RULE: Unit and integration tests must NEVER be disabled, removed, or bypassed.**

This rule is non-negotiable. If tests are failing:

1. **FIX THE CODE** - If the implementation is wrong
2. **FIX THE TESTS** - If the tests are incorrect
3. **NEVER** disable, skip, or lower coverage thresholds

See [CLAUDE.md](../../CLAUDE.md:199) for the complete policy on testing requirements.

## Test Architecture

```
flowchart TB
    subgraph "Test Pyramid"
        E2E["E2E Tests<br/>2 files"]
        INT["Integration Tests<br/>19 files"]
        UNIT["Unit Tests<br/>59 files"]
    end

    subgraph "Coverage Targets"
        UNIT_COV["Unit: 95%+"]
        INT_COV["Integration: 95%+"]
        TOTAL_COV["Combined: 95%+"]
    end

    UNIT --> UNIT_COV
    INT --> INT_COV
    E2E --> TOTAL_COV

    style UNIT fill:#76B900
    style INT fill:#3B82F6
    style E2E fill:#A855F7
```

### Test Categories

| Category        | Location                     | Count | Timeout | Coverage Target |
| --------------- | ---------------------------- | ----- | ------- | --------------- |
| **Unit Tests**  | `backend/tests/unit/`        | 59    | 1s      | 95%+            |
| **Integration** | `backend/tests/integration/` | 19    | 5s      | 95%+            |
| **E2E Tests**   | `backend/tests/e2e/`         | 2     | 30s     | -               |
| **GPU Tests**   | `backend/tests/gpu/`         | 1     | -       | -               |
| **Benchmarks**  | `backend/tests/benchmarks/`  | 3     | -       | -               |
| **Frontend**    | `frontend/src/**/*.test.ts`  | -     | -       | 95%+            |

## Running Tests

### Backend Tests

```bash
# Activate virtual environment first
source .venv/bin/activate

# All backend tests
pytest backend/tests/ -v

# Unit tests only
pytest backend/tests/unit/ -v

# Integration tests only
pytest backend/tests/integration/ -v

# E2E tests
pytest backend/tests/e2e/ -v

# With coverage report
pytest backend/tests/ -v --cov=backend --cov-report=html

# Disable timeouts for debugging
pytest backend/tests/ -v --timeout=0

# Parallel execution (4 workers)
pytest backend/tests/ -v -n 4
```

### Frontend Tests

```bash
cd frontend

# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Watch mode for development
npm run test -- --watch

# E2E tests (Playwright)
npm run test:e2e
```

### Full Validation

```bash
# Full validation suite (recommended before PRs)
./scripts/validate.sh

# Backend only
./scripts/validate.sh --backend

# Frontend only
./scripts/validate.sh --frontend

# Test runner with coverage
./scripts/test-runner.sh
```

## Pytest Configuration

The pytest configuration is defined in [pyproject.toml](../../pyproject.toml:91):

```toml
[tool.pytest.ini_options]
testpaths = ["backend/tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
addopts = "-n auto --dist=loadgroup -v --strict-markers --tb=short --timeout=1"
timeout_method = "thread"
```

### Test Markers

Available markers defined in [pyproject.toml](../../pyproject.toml:100):

| Marker                     | Purpose                 | Timeout |
| -------------------------- | ----------------------- | ------- |
| `@pytest.mark.asyncio`     | Mark as async test      | -       |
| `@pytest.mark.unit`        | Unit test marker        | 1s      |
| `@pytest.mark.integration` | Integration test marker | 5s      |
| `@pytest.mark.e2e`         | End-to-end test marker  | 30s     |
| `@pytest.mark.gpu`         | GPU-specific test       | -       |
| `@pytest.mark.slow`        | Legitimately slow test  | 30s     |

### Timeout Configuration

Timeouts are automatically assigned based on test location ([conftest.py](../../backend/tests/conftest.py:164)):

| Test Type         | Timeout | Configuration                                  |
| ----------------- | ------- | ---------------------------------------------- |
| Unit tests        | 1s      | Default from pyproject.toml                    |
| Integration tests | 5s      | Auto-assigned in pytest_collection_modifyitems |
| Slow-marked tests | 30s     | `@pytest.mark.slow`                            |
| CLI override      | varies  | `--timeout=N` (0 disables)                     |

## Fixtures

### Shared Fixtures

All shared fixtures are defined in [backend/tests/conftest.py](../../backend/tests/conftest.py:1). **DO NOT duplicate these in subdirectory conftest files.**

#### Database Fixtures

| Fixture           | Scope    | Description                                        |
| ----------------- | -------- | -------------------------------------------------- |
| `isolated_db`     | function | Function-scoped isolated PostgreSQL database       |
| `test_db`         | function | Callable session factory for unit tests            |
| `integration_env` | function | Sets DATABASE_URL, REDIS_URL, HSI_RUNTIME_ENV_PATH |
| `integration_db`  | function | Initializes PostgreSQL via testcontainers or local |
| `session`         | function | Savepoint-based transaction isolation              |
| `db_session`      | function | Direct AsyncSession access                         |

#### Redis Fixtures

| Fixture      | Scope    | Description                                             |
| ------------ | -------- | ------------------------------------------------------- |
| `mock_redis` | function | AsyncMock Redis client with pre-configured health_check |
| `real_redis` | function | Real Redis client via testcontainers (flushes DB 15)    |

#### HTTP Fixtures

| Fixture  | Scope    | Description                                             |
| -------- | -------- | ------------------------------------------------------- |
| `client` | function | httpx AsyncClient with ASGITransport (no server needed) |

#### Utility Fixtures

| Fixture                | Scope    | Description                                      |
| ---------------------- | -------- | ------------------------------------------------ |
| `reset_settings_cache` | autouse  | Clears settings cache before/after each test     |
| `unique_id(prefix)`    | function | Generates unique IDs for parallel test isolation |

### Example Fixture Usage

```python
import pytest
from backend.models import Camera

@pytest.mark.asyncio
async def test_camera_creation(isolated_db):
    """Test creating a camera with isolated database."""
    from backend.core.database import get_session

    async with get_session() as session:
        camera = Camera(id="test_cam", name="Test Camera")
        session.add(camera)
        await session.commit()

        assert camera.id == "test_cam"
```

## Writing Tests

### Unit Test Patterns

Unit tests verify individual components in isolation. All external dependencies (Redis, HTTP, file system) must be mocked.

See [backend/tests/unit/AGENTS.md](../../backend/tests/unit/AGENTS.md:1) for complete patterns.

```python
# Example: Mocking Redis
@pytest.fixture
def mock_redis_client():
    mock_client = AsyncMock(spec=RedisClient)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    return mock_client

# Example: Mocking HTTP clients
with patch("httpx.AsyncClient") as mock_http:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": "success"}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_http.return_value.__aenter__.return_value = mock_client
```

### Integration Test Patterns

Integration tests verify that multiple components work together correctly.

See [backend/tests/integration/AGENTS.md](../../backend/tests/integration/AGENTS.md:1) for complete patterns.

```python
@pytest.mark.asyncio
async def test_api_endpoint(client):
    """Test API endpoint with real database."""
    response = await client.get("/api/cameras")
    assert response.status_code == 200
    data = response.json()
    assert "cameras" in data
```

### Test Organization

Group related tests in classes:

```python
class TestCameraModel:
    """Tests for Camera model operations."""

    def test_create_camera_with_defaults(self, session):
        camera = Camera(id="test", name="Test Camera")
        session.add(camera)
        session.commit()
        assert camera.status == "online"

    def test_camera_validation_fails_empty_name(self, session):
        with pytest.raises(ValueError):
            Camera(id="test", name="")
```

### Async Testing

All async tests must use the `@pytest.mark.asyncio` decorator:

```python
@pytest.mark.asyncio
async def test_async_operation(isolated_db):
    async with get_session() as session:
        result = await some_async_function(session)
        assert result is not None
```

### Error Testing

Always test both success and failure paths:

```python
@pytest.mark.asyncio
async def test_handles_connection_error():
    """Test graceful handling of connection failures."""
    with patch("httpx.AsyncClient.post", side_effect=ConnectionError):
        result = await detector.detect_objects("test.jpg", "cam1", session)
        assert result == []  # Graceful failure
```

## Coverage Requirements

### Backend Coverage

Configured in [pyproject.toml](../../pyproject.toml:109):

```toml
[tool.coverage.run]
source = ["backend"]
omit = [
    "backend/tests/*",
    "backend/examples/*",
    "backend/main.py",
    "*/__pycache__/*",
]

[tool.coverage.report]
fail_under = 92
show_missing = true
```

### CI Coverage Thresholds

From [.github/workflows/ci.yml](../../.github/workflows/ci.yml:67):

| Test Type   | Threshold | Rationale                  |
| ----------- | --------- | -------------------------- |
| Unit        | 95%       | Standard per CLAUDE.md     |
| Integration | 95%       | Standard per CLAUDE.md     |
| Combined    | 95%       | Local validation threshold |

See pyproject.toml for the full coverage policy documentation.

### Generating Coverage Reports

```bash
# HTML report
pytest backend/tests/ --cov=backend --cov-report=html
open coverage/backend/index.html

# Terminal report with missing lines
pytest backend/tests/ --cov=backend --cov-report=term-missing
```

## Pre-commit and CI Integration

### Pre-push Hook

The `fast-test` hook runs unit tests before every push ([.pre-commit-config.yaml](../../.pre-commit-config.yaml:106)):

```yaml
- id: fast-test
  name: Quick Backend Tests (Unit Only)
  entry: bash -c 'source .venv/bin/activate && pytest backend/tests/unit/ -m "not slow" -q --tb=no -x -n0'
  stages: [pre-push]
```

### CI Pipeline

The CI workflow ([.github/workflows/ci.yml](../../.github/workflows/ci.yml:1)) runs:

1. **Backend Lint** - Ruff check and format
2. **Backend Type Check** - MyPy
3. **Backend Unit Tests** - 95% coverage threshold
4. **Backend Integration Tests** - 95% coverage threshold
5. **Frontend Lint** - ESLint
6. **Frontend Type Check** - TypeScript
7. **Frontend Tests** - Vitest (95% coverage threshold)
8. **Frontend E2E** - Playwright

All jobs must pass before a PR can be merged.

## Database Testing

### PostgreSQL via Testcontainers

Tests automatically start PostgreSQL via testcontainers when:

- `TEST_DATABASE_URL` is not set
- Local PostgreSQL on port 5432 is not available

### Local Development

With Podman/Docker running PostgreSQL:

```bash
podman-compose -f docker-compose.prod.yml up -d postgres redis
pytest backend/tests/ -v
```

Default URLs:

- PostgreSQL: `postgresql+asyncpg://security:security_dev_password@localhost:5432/security`
- Redis: `redis://localhost:6379/15` (DB 15 for test isolation)

### Parallel Test Isolation

Tests use these strategies for parallel isolation:

1. **Savepoint rollback** - Each test uses SAVEPOINT/ROLLBACK
2. **unique_id()** - Generate unique IDs to prevent conflicts
3. **Advisory locks** - Schema creation coordinated via `pg_advisory_lock(12345)`
4. **xdist_group markers** - Tests requiring sequential execution grouped

## Troubleshooting

### "Database not initialized"

- Use `isolated_db` or `integration_db` fixture
- Ensure `get_settings.cache_clear()` is called
- Check `await init_db()` is called after setting DATABASE_URL

### Parallel test conflicts

- Use `unique_id()` for test data IDs
- Add `@pytest.mark.xdist_group(name="group_name")` for sequential tests
- Check for global state mutations

### Timeout errors

- Add `@pytest.mark.slow` for tests needing > 1s
- Mock external services (HTTP, Redis)
- Check for background tasks not properly mocked

### Import errors

- Backend path is auto-added in conftest.py
- Check module names match file structure
- Activate virtual environment

## Related Documentation

- [Setup Guide](setup.md) - Development environment setup
- [Contributing Guide](contributing.md) - PR process and code standards
- [Code Patterns](patterns.md) - Testing patterns in detail
- [backend/tests/AGENTS.md](../../backend/tests/AGENTS.md) - Test infrastructure overview
