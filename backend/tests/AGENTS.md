# Backend Tests Directory

## Purpose

This directory contains all automated tests for the backend Python application. Tests are organized into five levels: unit tests (isolated component testing), integration tests (multi-component workflows), end-to-end tests (complete pipeline validation), GPU tests (AI service integration), and benchmarks (performance regression detection).

**For comprehensive testing patterns, fixtures, and best practices, see [`/docs/TESTING_GUIDE.md`](/docs/TESTING_GUIDE.md).**

## Directory Structure

```
backend/tests/
├── conftest.py              # Shared pytest fixtures and configuration
├── factories.py             # factory_boy factories for test data generation
├── strategies.py            # Hypothesis strategies for property-based testing
├── async_utils.py           # Async testing utilities and helpers
├── mock_utils.py            # Mock object creation utilities
├── matchers.py              # Custom test matchers (empty placeholder)
├── __init__.py              # Package initialization
├── unit/                    # Unit tests for isolated components (200 test files)
├── integration/             # Integration tests for API and multi-component workflows (60 test files)
├── e2e/                     # End-to-end pipeline integration tests (2 test files)
├── gpu/                     # GPU-specific AI service tests (1 test file)
├── benchmarks/              # Performance and complexity benchmarks (4 test files)
├── chaos/                   # Chaos engineering failure tests (5 test files)
├── contracts/               # API contract tests (1 test file)
├── security/                # Security vulnerability tests (3 test files)
├── fixtures/                # Test fixtures including sample images
├── check_syntax.py          # Syntax validation script
├── run_db_tests.sh          # Database test runner script
├── verify_database.py       # Database verification script
├── MATCHERS.md              # Custom matcher documentation (empty placeholder)
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

# Integration tests: parallel with worker-isolated databases (~33s for 1575 tests)
uv run pytest backend/tests/integration/ -n8 --dist=worksteal

# Integration tests: serial mode (legacy, ~169s)
uv run pytest backend/tests/integration/ -n0
```

**Integration Test Parallel Execution (NEM-1363):**

- Each pytest-xdist worker gets its own PostgreSQL database (`security_test_gw0`, etc.)
- Each worker uses a different Redis database number (0-15) for isolation
- Recommended: Use `-n8` for best balance of speed and reliability
- Benchmark: 169s serial -> 33s with 8 workers = **5.1x speedup**

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

### Factory Fixtures

| Fixture             | Scope    | Description                                       |
| ------------------- | -------- | ------------------------------------------------- |
| `camera_factory`    | function | CameraFactory for creating Camera instances       |
| `detection_factory` | function | DetectionFactory for creating Detection instances |
| `event_factory`     | function | EventFactory for creating Event instances         |
| `zone_factory`      | function | ZoneFactory for creating Zone instances           |

### Consolidated Mock Fixtures (NEM-1448)

These fixtures provide pre-configured mocks to reduce boilerplate in tests. Use them instead of creating inline mocks.

| Fixture                   | Type      | Description                                                    |
| ------------------------- | --------- | -------------------------------------------------------------- |
| `mock_db_session`         | AsyncMock | Mock AsyncSession with add/commit/refresh/execute configured   |
| `mock_db_session_context` | AsyncMock | Async context manager wrapping mock_db_session for get_session |
| `mock_http_response`      | MagicMock | Mock httpx.Response with status_code/json/text configured      |
| `mock_http_client`        | AsyncMock | Mock httpx.AsyncClient with all HTTP methods and context mgr   |
| `mock_detector_client`    | AsyncMock | Mock DetectorClient with detect_objects/health_check           |
| `mock_nemotron_client`    | AsyncMock | Mock NemotronAnalyzer with analyze/health_check                |
| `mock_redis_client`       | AsyncMock | Comprehensive Redis mock with get/set/publish/queue operations |
| `mock_settings`           | MagicMock | Mock Settings with database/redis/ai_host defaults             |
| `mock_baseline_service`   | MagicMock | Mock BaselineService for avoiding database in unit tests       |

**Usage Examples:**

```python
# Database session mock
@pytest.mark.asyncio
async def test_with_db(mock_db_session):
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = [camera]
    await service.do_something(mock_db_session)
    mock_db_session.commit.assert_called_once()

# HTTP client mock
@pytest.mark.asyncio
async def test_api_call(mock_http_client, mock_http_response):
    mock_http_response.json.return_value = {"detections": []}
    mock_http_client.post.return_value = mock_http_response
    with patch("httpx.AsyncClient", return_value=mock_http_client):
        result = await detector.detect(image_path)

# Database context manager mock
@pytest.mark.asyncio
async def test_with_context(mock_db_session, mock_db_session_context):
    with patch("backend.core.database.get_session", return_value=mock_db_session_context):
        await my_function()  # Uses async with get_session() as session:
        mock_db_session.commit.assert_called()

# Redis mock
@pytest.mark.asyncio
async def test_caching(mock_redis_client):
    mock_redis_client.get.return_value = '{"cached": "data"}'
    service = CacheService(redis=mock_redis_client)
    result = await service.get_cached("key")
```

## Test Data Factories (factory_boy)

Test fixtures use **factory_boy** for generating consistent test data. Factories are defined in `backend/tests/factories.py`.

### Available Factories

| Factory            | Model     | Common Traits                                                                         |
| ------------------ | --------- | ------------------------------------------------------------------------------------- |
| `CameraFactory`    | Camera    | `offline`, `with_last_seen`                                                           |
| `DetectionFactory` | Detection | `video`, `high_confidence`, `low_confidence`, `vehicle`, `animal`                     |
| `EventFactory`     | Event     | `low_risk`, `high_risk`, `critical`, `reviewed_event`, `fast_path`, `with_clip`       |
| `ZoneFactory`      | Zone      | `entry_point`, `driveway`, `sidewalk`, `yard`, `polygon`, `disabled`                  |
| `AlertFactory`     | Alert     | `low_severity`, `high_severity`, `critical`, `delivered`, `acknowledged`, `dismissed` |
| `AlertRuleFactory` | AlertRule | `low_severity`, `high_severity`, `critical`, `disabled`, `person_detection`           |

### Factory Usage Examples

```python
from backend.tests.factories import CameraFactory, DetectionFactory, EventFactory

# Create a camera with default values
camera = CameraFactory()

# Create a camera with specific values
camera = CameraFactory(id="front_door", name="Front Door")

# Create a camera using a trait
offline_camera = CameraFactory(offline=True)

# Create multiple cameras
cameras = CameraFactory.create_batch(5)

# Build without saving (for pure unit tests)
camera = CameraFactory.build()

# Create detection with video trait
video_detection = DetectionFactory(video=True, duration=30.5)

# Create high-risk event
high_risk_event = EventFactory(high_risk=True)

# Combine multiple traits
disabled_polygon_zone = ZoneFactory(polygon=True, disabled=True)
```

### Using Factory Fixtures

```python
def test_something(camera_factory, event_factory):
    """Test using factory fixtures from conftest.py."""
    camera = camera_factory(id="test_cam")
    event = event_factory(camera_id=camera.id, high_risk=True)
    # ... test assertions
```

### Helper Functions

```python
from backend.tests.factories import (
    create_camera_with_events,
    create_detection_batch_for_camera,
)

# Create camera with multiple associated events
camera, events = create_camera_with_events(
    camera_kwargs={"name": "Front Door"},
    num_events=5,
    event_kwargs={"risk_score": 75}
)

# Create multiple detections for a camera
detections = create_detection_batch_for_camera(
    "front_door",
    count=10,
    object_type="person",
)
```

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

## When to Use Parametrize vs Hypothesis

Choosing the right testing approach ensures maintainability and comprehensive coverage:

### Use @pytest.mark.parametrize for:

- **Known edge cases**: Specific boundary conditions you've identified (e.g., empty strings, None, -1)
- **Fixed test cases**: Predetermined inputs with expected outputs
- **Regression tests**: Specific bugs you've fixed and want to prevent
- **Exhaustive small sets**: All valid enum values, small finite sets
- **Documentation value**: When each case tells a story about requirements

**Example:**

```python
@pytest.mark.parametrize("invalid_input,reason", [
    ("", "empty string"),
    (None, "null value"),
    ("   ", "whitespace only"),
    (-1, "negative number"),
])
def test_validation_rejects_invalid_input(invalid_input, reason):
    assert validate(invalid_input) is False, f"Should reject: {reason}"
```

**Benefits:**

- Clear failure messages with the `reason` parameter
- Easy to add new edge cases as you discover them
- Test output shows exactly which case failed
- Great for code review: each case is visible and reviewable

### Use Hypothesis for:

- **Property-based testing**: Testing invariants that should hold for all inputs
- **Random input generation**: Finding edge cases you haven't thought of
- **Fuzzing**: Discovering unexpected behaviors with random data
- **Large input spaces**: When exhaustive testing isn't feasible
- **Mathematical properties**: Commutativity, associativity, idempotence, etc.

**Example:**

```python
from hypothesis import given
from hypothesis import strategies as st

@given(bbox=valid_bbox_xyxy_strategy())
def test_valid_bbox_always_passes_validation(bbox):
    """Property: Valid bboxes (x1 < x2, y1 < y2) are always valid."""
    assert is_valid_bbox(bbox) is True
```

**Benefits:**

- Discovers edge cases you didn't anticipate
- Tests hold for entire input domains, not just examples
- Hypothesis shrinks failing inputs to minimal reproducible cases
- Great for mathematical invariants and data structure properties

### Decision Guide

Ask yourself:

1. **Do I know the specific cases I want to test?** → Use parametrize
2. **Am I testing a property that should hold for all inputs?** → Use Hypothesis
3. **Am I testing a fixed set of values (enum, status codes)?** → Use parametrize
4. **Do I want to explore the input space for unknown edge cases?** → Use Hypothesis
5. **Is this a regression test for a specific bug?** → Use parametrize
6. **Am I validating mathematical properties?** → Use Hypothesis

### Combining Both Approaches

You can use both in the same test file:

```python
# Parametrize for known edge cases
@pytest.mark.parametrize("bbox", [
    (0, 0, 0, 0),      # Zero-size box
    (100, 100, 50, 50), # Inverted coordinates
])
def test_invalid_bbox_edge_cases(bbox):
    assert is_valid_bbox(bbox) is False

# Hypothesis for property-based testing
@given(bbox=valid_bbox_xyxy_strategy())
def test_valid_bbox_property(bbox):
    """Property: Valid construction always passes validation."""
    assert is_valid_bbox(bbox) is True
```

### When NOT to Use Parametrize

Avoid parametrize when:

- You have only 1-2 similar test cases (just write separate tests)
- The test logic changes significantly between cases (separate tests are clearer)
- Test setup differs for each case (use separate tests or fixtures instead)

### Related Issues

- **NEM-1450**: Expanded parametrize usage for edge cases in validation tests
- **NEM-1698**: Property-based tests for bbox validation mathematical properties

## Test Markers

Tests are organized using pytest markers for selective execution. Markers are auto-applied based on directory location and can also be explicitly set using decorators.

### Available Markers

| Marker        | Description                                   | Auto-applied             |
| ------------- | --------------------------------------------- | ------------------------ |
| `unit`        | Unit test (isolated component testing)        | Yes (`/unit/` directory) |
| `integration` | Integration test (multi-component workflows)  | Yes (`/integration/`)    |
| `e2e`         | End-to-end pipeline test                      | No                       |
| `gpu`         | GPU test (requires RTX A5500)                 | No                       |
| `slow`        | Legitimately slow test (30s timeout)          | No                       |
| `benchmark`   | Benchmark test (requires pytest-benchmark)    | No                       |
| `serial`      | Requires serial execution (no parallel)       | No                       |
| `flaky`       | Known to fail intermittently (quarantined)    | No                       |
| `network`     | Requires network access (for isolation in CI) | No                       |
| `db`          | Requires database access                      | No                       |
| `redis`       | Requires Redis access                         | No                       |

### Running Tests by Marker

```bash
# Run only unit tests
pytest -m unit backend/tests/

# Run only integration tests
pytest -m integration backend/tests/

# Exclude slow tests (faster CI runs)
pytest -m "not slow" backend/tests/

# Exclude network-dependent tests (offline development)
pytest -m "not network" backend/tests/

# Combine marker expressions
pytest -m "unit and not slow" backend/tests/
pytest -m "integration and not flaky" backend/tests/

# Run GPU tests only
pytest -m gpu backend/tests/gpu/

# Run everything except GPU and slow tests
pytest -m "not gpu and not slow" backend/tests/
```

### Auto-Applied Markers

The `pytest_collection_modifyitems` hook in `conftest.py` automatically applies markers:

- Tests in `backend/tests/unit/` receive the `unit` marker
- Tests in `backend/tests/integration/` receive the `integration` marker

This means you can run `pytest -m unit` without manually marking every test file.

### Explicit Marker Usage

For markers that are not auto-applied, use decorators:

```python
import pytest

@pytest.mark.slow
def test_large_batch_processing():
    """Test that processes 10,000 records."""
    ...

@pytest.mark.network
async def test_external_api_call():
    """Test that makes real HTTP requests."""
    ...

@pytest.mark.gpu
async def test_rtdetr_inference():
    """Test that requires GPU for object detection."""
    ...

@pytest.mark.flaky
def test_timing_sensitive_operation():
    """Test known to fail intermittently."""
    ...
```

## Coverage Requirements

- **Unit Tests**: 85%+ coverage (CI unit test job)
- **Combined**: 95%+ coverage for all backend code (`pyproject.toml` fail_under)
- **Reports**: HTML reports via `--cov-report=html`

## Test Categories

### Unit Tests (`unit/`) - 200 test files

Tests for individual components in isolation with all external dependencies mocked.
Includes property-based tests using **Hypothesis** for model invariants.

Subdirectories:

- **api/routes/**: API route unit tests (21 files) - AI audit, cameras, DLQ, enrichment, events, etc.
- **api/schemas/**: Pydantic schema validation tests (8 files)
- **api/helpers/**: API helper function tests (1 file) - enrichment transformers
- **api/middleware/**: API middleware tests (1 file) - request timing
- **core/**: Infrastructure tests (36 files) - config, database, redis, logging, middleware, TLS
- **models/**: ORM model tests (20 files) - Camera, Detection, Event, Alert, Zone, GPUStats
- **routes/**: Additional route tests (14 files) - admin, alerts, audit, cameras, events, etc.
- **services/**: Business logic tests (87 files) - AI pipeline, broadcasters, enrichment, loaders
- **middleware/**: Core middleware tests (1 file) - correlation ID
- **integration/**: Integration helper tests (1 file) - test helpers
- **scripts/**: Migration script tests (1 file)
- **Root level**: Utility tests (10 files) - async_utils, mock_utils, benchmarks, main, etc.

### Integration Tests (`integration/`) - 60 test files

Tests for multi-component workflows with real database and mocked Redis.
**Now support parallel execution** with pytest-xdist (5x speedup with 8 workers).

Categories:

- **API endpoints**: admin, alerts, AI audit, cameras, detections, events, logs, media, metrics, zones (21 files)
- **WebSocket**: Connection handling, broadcasting, authentication, cleanup (3 files)
- **Services**: Batch aggregation, detector client, file watcher, health monitor, cache, cleanup (12 files)
- **Models and Database**: Alert models, baseline, database operations, model cascades (8 files)
- **Error Handling**: API errors, database isolation, transaction rollback, HTTP error codes (5 files)
- **Pipeline and Full Stack**: Circuit breaker, enrichment, event search, full stack, pipeline E2E (7 files)
- **Infrastructure**: Alembic migrations, GitHub workflows, trigram indexes (3 files)
- **Security**: Media file serving security (1 file)

### End-to-End Tests (`e2e/`) - 2 test files

Complete pipeline tests from file detection to event creation.

- `test_pipeline_integration.py`: E2E with mocked AI services
- `test_gpu_pipeline.py`: E2E with real or mocked GPU services

### GPU Tests (`gpu/`) - 1 test file

Tests for RT-DETRv2 and Nemotron service integration.

- `test_detector_integration.py`: GPU service health, inference, performance

### Benchmarks (`benchmarks/`) - 4 test files

Performance and complexity regression detection.

- `test_api_benchmarks.py`: Response time measurements
- `test_bigo.py`: O(n) complexity verification
- `test_memory.py`: Memory usage limits (Linux only)
- `test_performance.py`: Core performance regression benchmarks

### Chaos Tests (`chaos/`) - 5 test files

Chaos engineering tests that inject faults into services to ensure graceful degradation.

- `test_rtdetr_failures.py`: RT-DETR object detection service failures
- `test_redis_failures.py`: Redis cache/queue service failures
- `test_database_failures.py`: PostgreSQL database failures
- `test_nemotron_failures.py`: Nemotron LLM service failures
- `test_network_conditions.py`: Network latency and reliability issues

### Contract Tests (`contracts/`) - 1 test file

API contract tests for response schema validation.

- `test_api_contracts.py`: API response schema validation (21+ tests)

### Security Tests (`security/`) - 3 test files

Security vulnerability tests for common web attacks.

- `test_api_security.py`: SQL injection, XSS, path traversal, rate limiting, CORS
- `test_auth_security.py`: API key authentication, hashing, exempt paths
- `test_input_validation.py`: Schema validation, query parameters, encoding

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
- `chaos/AGENTS.md` - Chaos engineering tests
- `contracts/AGENTS.md` - API contract tests
- `security/AGENTS.md` - Security vulnerability tests
- `fixtures/AGENTS.md` - Test fixtures
- `gpu/AGENTS.md` - GPU service tests
- `/backend/AGENTS.md` - Backend architecture
- `/CLAUDE.md` - Project instructions
