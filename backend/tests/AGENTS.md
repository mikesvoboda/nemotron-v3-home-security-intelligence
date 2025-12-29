# Backend Tests Directory

## Purpose

This directory contains all automated tests for the backend Python application. Tests are organized into four levels: unit tests (isolated component testing), integration tests (multi-component workflows), end-to-end tests (complete pipeline validation), and benchmarks (performance regression detection).

## Directory Structure

```
backend/tests/
├── conftest.py              # Shared pytest fixtures and configuration
├── unit/                    # Unit tests for isolated components (42 test files)
├── integration/             # Integration tests for API and multi-component workflows (18 test files)
├── e2e/                     # End-to-end pipeline integration tests (1 test file)
├── benchmarks/              # Performance and complexity benchmarks (3 test files)
├── check_syntax.py          # Syntax validation script
├── verify_database.py       # Database verification script
├── run_db_tests.sh          # Database test runner script
├── DATABASE_TEST_FIXES.md   # Documentation for database test fixes
└── WEBSOCKET_TEST_SUMMARY.md # WebSocket testing documentation
```

## Test Organization

### Unit Tests (`unit/`)

Tests for individual components in isolation:

- **Core**: Configuration, database connections, Redis client, logging, metrics
- **Models**: Database model definitions and relationships
- **Services**: Business logic (file watcher, detectors, analyzers, aggregators, broadcasters, video processor)
- **API Routes**: Individual endpoint handlers (cameras, events, detections, system, logs, media, websocket)
- **Middleware**: Authentication, request handling
- **Video Support**: Video file detection, validation, streaming, thumbnails
- **Mocking**: All external dependencies (HTTP, Redis, file system) are mocked

**Total**: 42 test files covering core functionality

### Integration Tests (`integration/`)

Tests for complete workflows across multiple components:

- **API endpoints**: FastAPI routes with real database operations
- **Full stack**: Database workflows from camera creation to event generation
- **Media serving**: File serving and security validation
- **WebSocket**: Real-time communication channels
- **Service integration**: Batch aggregator, detector client, file watcher, health monitor, Nemotron analyzer
- **GitHub Workflows**: CI/CD pipeline validation
- **Mocking**: Redis mocked, database uses test PostgreSQL instance

**Total**: 18 test files covering API and workflow integration

### End-to-End Tests (`e2e/`)

Tests for the complete AI pipeline flow:

- **Complete pipeline**: File detection -> RT-DETRv2 -> Batch aggregation -> Nemotron -> Event creation -> WebSocket broadcast
- **Error handling**: Service failures, timeouts, fallback behavior
- **Batch logic**: Time windows, idle timeouts, cleanup
- **Relationships**: Database integrity across cameras, detections, events
- **Mocking**: External AI services mocked, database and business logic real

**Total**: 1 comprehensive test file with 8+ E2E scenarios

### Benchmarks (`benchmarks/`)

Performance and complexity tests:

- **API Benchmarks**: Response time measurements for critical endpoints
- **Big-O Complexity**: Algorithmic complexity verification (O(n) vs O(n^2))
- **Memory Profiling**: Memory usage limits for repeated operations (Linux only)
- **Regression Detection**: Baseline comparison for performance degradation

**Total**: 3 test files with performance validation

## Shared Fixtures (conftest.py)

All shared fixtures are defined in `backend/tests/conftest.py`. **DO NOT duplicate these fixtures in subdirectory conftest files or individual test files.**

### Unit Test Fixtures

#### `isolated_db`

- **Scope**: Function
- **Purpose**: Creates isolated temporary database for each test
- **Usage**: Ensures clean database state, no test pollution
- **Cleanup**: Automatically restores environment after test

```python
@pytest.mark.asyncio
async def test_database_operation(isolated_db):
    from backend.core.database import get_session

    async with get_session() as session:
        # Test code here
        pass
```

#### `test_db`

- **Scope**: Function
- **Purpose**: Provides a callable session factory for unit tests
- **Usage**: Returns `get_session` function for database access
- **Cleanup**: Automatic cleanup and environment restoration

#### `reset_settings_cache`

- **Scope**: Auto-used for all tests
- **Purpose**: Clears settings cache before/after each test
- **Usage**: Prevents global state leakage between tests

### Integration/E2E Test Fixtures

These fixtures are shared across ALL integration and E2E tests. They are defined once in `backend/tests/conftest.py` and inherited by all subdirectories.

#### `integration_env`

- **Scope**: Function
- **Purpose**: Sets DATABASE_URL, REDIS_URL, and HSI_RUNTIME_ENV_PATH environment variables
- **Usage**: Environment setup only; use `integration_db` if database needs initialization
- **Cleanup**: Restores original environment variables after test

#### `integration_db`

- **Scope**: Function
- **Purpose**: Initializes temporary test database with all tables
- **Depends on**: `integration_env`
- **Usage**: Use for any test that needs database access

```python
@pytest.mark.asyncio
async def test_full_workflow(integration_db):
    from backend.core.database import get_session

    async with get_session() as session:
        # Test code here with real database
        pass
```

#### `mock_redis`

- **Scope**: Function
- **Purpose**: Mocks Redis client so tests don't require actual Redis server
- **Patches**: `backend.core.redis._redis_client`, `init_redis`, `close_redis`
- **Pre-configured**: `health_check()` returns healthy status

```python
@pytest.mark.asyncio
async def test_with_redis(integration_db, mock_redis):
    mock_redis.get.return_value = "test_value"
    # Test code here
```

#### `db_session`

- **Scope**: Function
- **Purpose**: Yields a live AsyncSession for direct database access
- **Depends on**: `integration_db`
- **Usage**: When you need direct session access without `get_session()` context manager

#### `client`

- **Scope**: Function
- **Purpose**: httpx AsyncClient bound to FastAPI app for API testing
- **Depends on**: `integration_db`, `mock_redis`
- **Patches**: DB init/close in lifespan, Redis init/close

```python
@pytest.mark.asyncio
async def test_api_endpoint(client):
    response = await client.get("/api/system/health")
    assert response.status_code == 200
```

### Fixture Convention: DO NOT Duplicate

**CRITICAL**: Never define these fixtures in subdirectory conftest files:

- `integration_env`
- `integration_db`
- `mock_redis`
- `db_session`
- `client`

Instead, all tests should use the shared fixtures from `backend/tests/conftest.py` directly.

## Test Timeout Requirements

**CRITICAL**: All tests must complete within 30 seconds. This ensures fast CI/CD pipelines and prevents hanging tests.

```bash
# Run tests with 30-second timeout enforcement
pytest backend/tests/ -v --timeout=30
```

Tests that exceed 30 seconds indicate:

- Missing or improper mocking of external services
- Slow database operations that should be optimized
- Background tasks not properly mocked
- Network calls that should be stubbed

### How to Fix Slow Tests

1. **Mock external services**: Use `mock_redis`, patch HTTP clients
2. **Mock background services**: Patch GPUMonitor, CleanupService, SystemBroadcaster
3. **Use async sleep sparingly**: Only for testing timing behavior, keep durations short
4. **Optimize database operations**: Use bulk operations where possible

## Running Tests

### All tests

```bash
# From project root (with 30s timeout)
pytest backend/tests/ -v --timeout=30

# With coverage
pytest backend/tests/ -v --cov=backend --cov-report=html --timeout=30

# With coverage threshold check (95%+)
pytest backend/tests/ -v --cov=backend --cov-report=term-missing --cov-fail-under=95 --timeout=30
```

### Unit tests only

```bash
pytest backend/tests/unit/ -v
```

### Integration tests only

```bash
pytest backend/tests/integration/ -v
```

### End-to-end tests only

```bash
pytest backend/tests/e2e/ -v

# With E2E marker
pytest -m e2e -v
```

### Benchmark tests

```bash
# API response time benchmarks
pytest backend/tests/benchmarks/test_api_benchmarks.py --benchmark-only

# Big-O complexity tests
pytest backend/tests/benchmarks/test_bigo.py -v

# Memory profiling (Linux only)
pytest backend/tests/benchmarks/test_memory.py --memray -v

# Compare against baseline
pytest backend/tests/benchmarks/ --benchmark-compare
```

### Specific test file

```bash
pytest backend/tests/unit/test_models.py -v
```

### Specific test

```bash
pytest backend/tests/unit/test_models.py::TestCameraModel::test_create_camera -v
```

### With verbose debugging

```bash
pytest backend/tests/ -vv -s --log-cli-level=DEBUG
```

## Coverage Requirements

- **Target**: 95%+ coverage for all backend code
- **Enforced by**: Pre-commit hooks (ruff, mypy, pytest)
- **Command**: `pytest backend/tests/ -v --cov=backend --cov-report=term-missing`
- **Current status**: Unit tests at 95%+, integration tests comprehensive

## Test Patterns

### Database Testing

- Use `isolated_db` fixture for clean database state
- Tests run against temporary test databases
- Each test gets fresh database instance
- Automatic cleanup after test completion

```python
@pytest.mark.asyncio
async def test_create_camera(isolated_db):
    async with get_session() as session:
        camera = Camera(id="test", name="Test Camera")
        session.add(camera)
        await session.commit()
        assert camera.id == "test"
```

### Async Testing

- All async tests use `@pytest.mark.asyncio` decorator
- Configured in `pytest.ini` with `asyncio_mode = auto`
- Proper handling of async context managers and sessions

```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result is not None
```

### Mocking Strategy

- **Unit tests**: Mock all external dependencies (HTTP, Redis, file system)
- **Integration tests**: Mock Redis, use real database
- **E2E tests**: Mock external AI services, use real business logic and database
- **Benchmarks**: Mock Redis, use real database for realistic measurements
- Common mocks: Redis client, HTTP clients (httpx), file system operations

### Fixture Organization

- Shared fixtures in `conftest.py` (project root and subdirectories)
- Test-specific fixtures in individual test files
- Use function scope for isolation, session scope sparingly

## Test Dependencies

All test dependencies are in `backend/requirements.txt`:

- `pytest>=7.4.0` - Test framework
- `pytest-asyncio>=0.21.0` - Async test support
- `pytest-cov>=4.1.0` - Coverage reporting
- `pytest-benchmark>=4.0.0` - Performance benchmarks
- `httpx>=0.25.0` - Async HTTP client for API testing

Optional dependencies:

- `pytest-memray` - Memory profiling (Linux only)
- `big-o` - Algorithmic complexity testing

## Testing Philosophy

1. **Isolation**: Each test should be independent and not rely on others
2. **Clarity**: Test names describe what is being tested and expected outcome
3. **Coverage**: Test both happy paths and error conditions
4. **Speed**: Unit tests fast (<10s total), integration moderate (<30s), E2E comprehensive (<1min)
5. **Maintainability**: Keep tests simple and readable, avoid complex test logic

## Test Database Isolation

### Test Database

Tests use temporary test databases. Each test function gets a fresh database instance that is automatically cleaned up after the test completes. The test suite can use either in-memory SQLite for speed or PostgreSQL for production parity.

### Redis

Tests use Redis database index 15 (`redis://localhost:6379/15`) to isolate test data from development data.

| Purpose     | Database Index | URL                         |
| ----------- | -------------- | --------------------------- |
| Production  | 0              | `redis://localhost:6379/0`  |
| Development | 0 (default)    | `redis://localhost:6379/0`  |
| **Testing** | **15**         | `redis://localhost:6379/15` |

**Key points:**

- The test Redis URL is set in `conftest.py` fixtures (`integration_env`, `integration_db`, etc.)
- `FLUSHDB` is called by pre-commit hooks before running tests (see `.pre-commit-config.yaml`)
- `FLUSHDB` is safe because it only affects database 15, leaving dev/prod data untouched
- **Never use database 15 for non-test purposes**

**Why database 15?**

- Redis supports 16 databases (0-15) by default
- Database 15 is the highest index, minimizing collision risk with other uses
- It provides clear separation from the default database 0 used in development

**Pre-commit integration:**
The pre-commit hook runs `redis-cli -n 15 FLUSHDB` before executing tests to ensure a clean slate:

```bash
redis-cli -n 15 FLUSHDB > /dev/null 2>&1
```

## Common Test Scenarios

### Testing Database Operations

```python
@pytest.mark.asyncio
async def test_database_operation(isolated_db):
    from backend.core.database import get_session

    async with get_session() as session:
        # Test code here
        pass
```

### Testing API Endpoints

```python
@pytest.mark.asyncio
async def test_api_endpoint(client):
    response = await client.get("/api/endpoint")
    assert response.status_code == 200
```

### Testing with Mocked Redis

```python
@pytest.mark.asyncio
async def test_with_redis(mock_redis_client):
    mock_redis_client.get.return_value = "test_value"
    # Test code here
```

### Testing with Mocked HTTP

```python
with patch("httpx.AsyncClient") as mock_http:
    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value={"result": "success"})
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_http.return_value.__aenter__.return_value = mock_client
    # Test code here
```

## Test Statistics

### Overall Test Count

- **Unit tests**: 42 test files covering core, models, services, API routes
- **Integration tests**: 18 test files covering API endpoints and workflows
- **E2E tests**: 8+ comprehensive scenarios in 1 file
- **Benchmarks**: 3 test files for performance validation
- **Total**: Comprehensive coverage of 95%+ of backend code

### Coverage by Component

- **Core** (config, database, redis, logging): 98%+
- **Models** (Camera, Detection, Event, GPUStats, Log): 98%+
- **Services** (AI pipeline, broadcasters, cleanup, video processor): 95%+
- **API Routes** (REST endpoints, logs, media): 95%+
- **WebSocket** (real-time channels): 90%+

## Troubleshooting

### Tests fail with "Database not initialized"

- Ensure you're using `isolated_db` fixture
- Check that `get_settings.cache_clear()` is being called
- Verify `await init_db()` is called after setting environment

### Tests interfere with each other

- Verify each test uses function-scoped fixtures
- Check for shared global state
- Use `isolated_db` for database tests
- Clear settings cache between tests

### Async errors

- Ensure test has `@pytest.mark.asyncio` decorator
- Check all async functions are awaited
- Verify async context managers use `async with`

### Coverage gaps

- Run with `--cov-report=term-missing` to see uncovered lines
- Check if branches are covered (use `--cov-branch`)
- Add tests for error conditions and edge cases

### Import errors

- Ensure backend path is in sys.path (conftest.py handles this)
- Check module names match file structure

### Mock not working

- Verify mock path matches import path in source
- Use `spec=ClassName` to catch attribute errors
- Check mock is applied before function call

## Pre-commit Integration

All tests are run automatically on commit via pre-commit hooks:

```bash
# Run pre-commit checks manually
pre-commit run --all-files

# Tests included in pre-commit:
# - ruff check (linting)
# - ruff format (formatting)
# - mypy (type checking)
# - pytest (95% coverage required)
```

**CRITICAL**: Never bypass pre-commit hooks with `--no-verify`

## Test Development Workflow

1. **Read AGENTS.md**: Understand test structure for the area you're working on
2. **Write test first** (TDD): Define expected behavior before implementation
3. **Run test** (should fail): Verify test catches the missing functionality
4. **Implement feature**: Write minimal code to make test pass
5. **Run test** (should pass): Verify implementation works
6. **Refactor**: Clean up code while keeping tests green
7. **Check coverage**: Ensure 95%+ coverage maintained

## Next Steps for AI Agents

1. **Read subdirectory AGENTS.md**: Explore `unit/`, `integration/`, `e2e/`, or `benchmarks/` for specific test patterns
2. **Understand fixtures**: Check conftest.py files for available test fixtures
3. **Run tests**: Use Bash tool with pytest command to verify current state
4. **Add tests**: Follow existing patterns for new functionality
5. **Verify coverage**: Run with --cov flag to ensure 95%+ coverage
6. **Never skip tests**: All features must have tests before being marked complete

## Related Documentation

- `/backend/tests/unit/AGENTS.md` - Unit test patterns and fixtures
- `/backend/tests/integration/AGENTS.md` - Integration test architecture
- `/backend/tests/e2e/AGENTS.md` - End-to-end pipeline testing
- `/backend/tests/benchmarks/AGENTS.md` - Performance benchmarks
- `/backend/AGENTS.md` - Backend architecture overview
- `/CLAUDE.md` - Project instructions and testing requirements
