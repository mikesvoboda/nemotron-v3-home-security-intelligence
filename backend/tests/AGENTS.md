# Backend Tests Directory

## Purpose

This directory contains all automated tests for the backend Python application. Tests are organized into five levels: unit tests (isolated component testing), integration tests (multi-component workflows), end-to-end tests (complete pipeline validation), GPU tests (AI service integration), and benchmarks (performance regression detection).

## Directory Structure

```
backend/tests/
├── conftest.py              # Shared pytest fixtures and configuration
├── __init__.py              # Package initialization
├── unit/                    # Unit tests for isolated components (150 test files)
├── integration/             # Integration tests for API and multi-component workflows (55 test files)
├── e2e/                     # End-to-end pipeline integration tests (2 test files)
├── gpu/                     # GPU-specific AI service tests (1 test file)
├── benchmarks/              # Performance and complexity benchmarks (3 test files)
├── fixtures/                # Test fixtures including sample images
├── check_syntax.py          # Syntax validation script
├── run_db_tests.sh          # Database test runner script
├── verify_database.py       # Database verification script
├── DATABASE_TEST_FIXES.md   # Documentation for database test fixes
└── WEBSOCKET_TEST_SUMMARY.md # WebSocket testing documentation
```

## Running Tests

### All tests

```bash
# From project root
pytest backend/tests/ -v

# With 30s timeout (CI default)
pytest backend/tests/ -v --timeout=30

# With coverage
pytest backend/tests/ -v --cov=backend --cov-report=html

# Disable timeouts (for debugging)
pytest backend/tests/ -v --timeout=0
```

### By category

```bash
# Unit tests only
pytest backend/tests/unit/ -v

# Integration tests only
pytest backend/tests/integration/ -v

# End-to-end tests
pytest backend/tests/e2e/ -v

# GPU tests (requires GPU services)
pytest backend/tests/gpu/ -v -m gpu

# Benchmarks
pytest backend/tests/benchmarks/ -v --benchmark-only
```

### Parallel execution

```bash
# Unit tests: parallel with worksteal scheduler (~10s for 7193 tests)
uv run pytest backend/tests/unit/ -n auto --dist=worksteal

# Integration tests: serial due to shared database state (~70s for 1499 tests)
uv run pytest backend/tests/integration/ -n0
```

**Note:** Integration tests must run serially (`-n0`) because they share database state
through fixtures that clean tables. Use DELETE instead of TRUNCATE in test fixtures
to avoid AccessExclusiveLock deadlocks.

## Shared Fixtures (conftest.py)

All shared fixtures are defined in `backend/tests/conftest.py`. DO NOT duplicate these in subdirectory conftest files.

### Database Fixtures

| Fixture           | Scope    | Description                                        |
| ----------------- | -------- | -------------------------------------------------- |
| `isolated_db`     | function | Function-scoped isolated PostgreSQL database       |
| `test_db`         | function | Callable session factory for unit tests            |
| `integration_env` | function | Sets DATABASE_URL, REDIS_URL, HSI_RUNTIME_ENV_PATH |
| `integration_db`  | function | Initializes PostgreSQL via testcontainers or local |
| `session`         | function | Savepoint-based transaction isolation              |
| `db_session`      | function | Direct AsyncSession access                         |

### Redis Fixtures

| Fixture      | Scope    | Description                                             |
| ------------ | -------- | ------------------------------------------------------- |
| `mock_redis` | function | AsyncMock Redis client with pre-configured health_check |
| `real_redis` | function | Real Redis client via testcontainers (flushes DB 15)    |

### HTTP Fixtures

| Fixture  | Scope    | Description                                             |
| -------- | -------- | ------------------------------------------------------- |
| `client` | function | httpx AsyncClient with ASGITransport (no server needed) |

### Utility Fixtures

| Fixture                | Scope    | Description                                      |
| ---------------------- | -------- | ------------------------------------------------ |
| `reset_settings_cache` | autouse  | Clears settings cache before/after each test     |
| `unique_id(prefix)`    | function | Generates unique IDs for parallel test isolation |

## Database Infrastructure

### PostgreSQL via Testcontainers

Tests automatically start PostgreSQL via testcontainers when:

- `TEST_DATABASE_URL` is not set
- Local PostgreSQL on port 5432 is not available

Container lifecycle:

- Started in `pytest_configure` (once per session)
- Stopped in `pytest_unconfigure`

### Local Development

With Podman/Docker running PostgreSQL:

```bash
podman-compose -f docker-compose.prod.yml up -d postgres redis
pytest backend/tests/ -v
```

Default URLs (set in `.env` or via `./setup.sh`):

- PostgreSQL: `postgresql+asyncpg://security:<your-password>@localhost:5432/security`
- Redis: `redis://localhost:6379/15` (DB 15 for test isolation)

> **Note:** Tests use the password configured in your `.env` file. Run `./setup.sh` to generate secure credentials.

### Parallel Test Isolation

Tests use these strategies for parallel isolation:

1. **Savepoint rollback**: Each test uses SAVEPOINT/ROLLBACK for transaction isolation
2. **unique_id()**: Generate unique IDs to prevent primary key conflicts
3. **DELETE over TRUNCATE**: Use `DELETE FROM` instead of `TRUNCATE TABLE` to avoid AccessExclusiveLock
4. **Unit/Integration separation**: Unit tests run parallel, integration tests run serial

**Important:** Integration tests share database state and cannot run in parallel. Full parallel
execution would require module-scoped testcontainers (one container per test module).

## Test Timeout Configuration

Timeouts are applied automatically based on test location:

| Test Type         | Timeout | Configuration                                  |
| ----------------- | ------- | ---------------------------------------------- |
| Unit tests        | 1s      | Default from pyproject.toml                    |
| Integration tests | 5s      | Auto-assigned in pytest_collection_modifyitems |
| Slow-marked tests | 30s     | `@pytest.mark.slow`                            |
| CLI override      | varies  | `--timeout=N` (0 disables)                     |

## Coverage Requirements

- **Unit Tests**: 85%+ coverage (CI unit test job)
- **Combined**: 95%+ coverage for all backend code (`pyproject.toml` fail_under)
- **Reports**: HTML reports via `--cov-report=html`

## Test Categories

### Unit Tests (`unit/`) - 150 test files

Tests for individual components in isolation with all external dependencies mocked.
Includes property-based tests using **Hypothesis** for model invariants.

Subdirectories:

- **api/routes/**: API route unit tests (17 files) - AI audit, cameras, DLQ, enrichment, events, etc.
- **api/schemas/**: Pydantic schema validation tests (5 files)
- **core/**: Infrastructure tests (28 files) - config, database, redis, logging, middleware, TLS
- **models/**: ORM model tests (16 files) - Camera, Detection, Event, Alert, Zone, GPUStats
- **routes/**: Additional route tests (13 files) - admin, alerts, audit, cameras, events, etc.
- **services/**: Business logic tests (71 files) - AI pipeline, broadcasters, enrichment, loaders
- **scripts/**: Migration script tests (1 file)

### Integration Tests (`integration/`) - 55 test files

Tests for multi-component workflows with real database and mocked Redis.
**Must run serially** (`-n0`) due to shared database state.

Categories:

- **API endpoints**: admin, alerts, AI audit, cameras, detections, events, logs, media, metrics, zones
- **WebSocket**: Connection handling, broadcasting, authentication, cleanup
- **Services**: Batch aggregation, detector client, file watcher, health monitor, cache, cleanup
- **Full stack**: Camera -> Detection -> Event workflows, pipeline E2E
- **Security**: Path traversal prevention, file type validation, error handling
- **Database**: Migrations, model cascades, transaction rollback, Redis pub/sub

### End-to-End Tests (`e2e/`) - 2 test files

Complete pipeline tests from file detection to event creation.

- `test_pipeline_integration.py`: E2E with mocked AI services
- `test_gpu_pipeline.py`: E2E with real or mocked GPU services

### GPU Tests (`gpu/`) - 1 test file

Tests for RT-DETRv2 and Nemotron service integration.

- `test_detector_integration.py`: GPU service health, inference, performance

### Benchmarks (`benchmarks/`) - 3 test files

Performance and complexity regression detection.

- `test_api_benchmarks.py`: Response time measurements
- `test_bigo.py`: O(n) complexity verification
- `test_memory.py`: Memory usage limits (Linux only)

### Fixtures (`fixtures/`)

Test fixtures and sample data.

- `images/pipeline_test/`: 14 JPEG images for testing (person, pet, vehicle detection)

## Pre-commit Integration

Tests are run via pre-commit hooks:

```bash
# Install hooks
pre-commit install
pre-commit install --hook-type pre-push

# Manual run
pre-commit run --all-files
```

Pre-push hook runs `pytest backend/tests/unit/ -v`.

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

## Async Testing Best Practices

### Framework Decision: pytest-asyncio vs pytest-anyio

This project uses **pytest-asyncio** (not pytest-anyio) for the following reasons:

1. **Existing Infrastructure**: 7000+ tests use pytest-asyncio with `asyncio_mode = "auto"`
2. **Backend-specific**: Only asyncio is used (no trio support needed)
3. **Fixture compatibility**: Function-scoped fixtures with testcontainers work well
4. **Migration cost**: Converting would require extensive fixture updates
5. **Maturity**: Better documentation for FastAPI + SQLAlchemy + httpx stack

### Async Testing Utilities

The `backend/tests/async_utils.py` module provides standardized patterns:

#### Mock Async Context Managers

**Old verbose pattern (avoid):**

```python
mock_client = AsyncMock()
mock_client.__aenter__ = AsyncMock(return_value=mock_client)
mock_client.__aexit__ = AsyncMock(return_value=None)
mock_client_class.return_value = mock_client
```

**New pattern (preferred):**

```python
from backend.tests.async_utils import AsyncClientMock, create_mock_db_context

# For HTTP clients
mock = AsyncClientMock(
    get_responses={"/health": {"status": "healthy"}},
    post_responses={"/detect": {"detections": []}},
)
async with mock.client() as client:
    response = await client.get("/health")

# For database sessions
mock_session = create_async_session_mock(execute_results=[...])
mock_context = create_mock_db_context(mock_session)
```

#### Timeout Protection

Use for flaky operations or tests that might hang:

```python
from backend.tests.async_utils import async_timeout, with_timeout

# Context manager style
async with async_timeout(5.0, operation="health check"):
    await client.check_health()

# Function wrapper style
result = await with_timeout(
    client.get_data(),
    timeout=5.0,
    operation="fetching data",
)
```

#### Concurrent Testing

Test concurrent operations properly:

```python
from backend.tests.async_utils import run_concurrent_tasks, simulate_concurrent_requests

# Run multiple coroutines concurrently
result = await run_concurrent_tasks(
    client.get("/endpoint1"),
    client.get("/endpoint2"),
    client.get("/endpoint3"),
)
assert result.all_succeeded
assert len(result.results) == 3

# Simulate load testing
result = await simulate_concurrent_requests(
    lambda: client.get("/api/health"),
    count=10,
    delay_between=0.01,
)
```

### AsyncMock Best Practices

1. **Use spec parameter** to catch typos in method names:

   ```python
   from backend.core.redis import RedisClient
   mock_client = MagicMock(spec=RedisClient)
   ```

2. **Mock at the right level** - mock the class, not the instance:

   ```python
   # Good: Mock the class constructor
   with patch("httpx.AsyncClient") as mock_class:
       mock_class.return_value = mock_client

   # Avoid: Mock the global module
   with patch("backend.services.foo._client", mock_client):
       ...
   ```

3. **Use create_async_session_mock()** for database mocking:

   ```python
   mock_session = create_async_session_mock(
       execute_results=[mock_camera_result, mock_detection_result],
   )
   ```

### Common Async Testing Patterns

#### Testing Async Generators

```python
async def test_async_generator():
    results = []
    async for item in async_generator_function():
        results.append(item)
    assert len(results) == expected_count
```

#### Testing WebSocket Connections

```python
async def test_websocket_connection(client):
    async with client.websocket_connect("/ws") as ws:
        await ws.send_json({"type": "subscribe"})
        response = await ws.receive_json()
        assert response["type"] == "subscribed"
```

#### Testing Background Tasks

```python
async def test_background_task():
    task = asyncio.create_task(background_function())
    try:
        # Wait for task to complete or timeout
        await asyncio.wait_for(task, timeout=5.0)
    except asyncio.TimeoutError:
        task.cancel()
        pytest.fail("Background task did not complete")
```

### Avoiding Flaky Async Tests

1. **Use explicit timeouts** instead of relying on default behavior
2. **Mock time-dependent operations** (use `freezegun` or mock `asyncio.sleep`)
3. **Avoid race conditions** by using proper synchronization primitives
4. **Clean up resources** in finally blocks or fixtures
5. **Use unique IDs** (`unique_id()`) for test data to avoid conflicts

## Related Documentation

- `unit/AGENTS.md` - Unit test patterns
- `integration/AGENTS.md` - Integration test architecture
- `e2e/AGENTS.md` - End-to-end pipeline testing
- `benchmarks/AGENTS.md` - Performance benchmarks
- `/backend/AGENTS.md` - Backend architecture
- `/CLAUDE.md` - Project instructions
